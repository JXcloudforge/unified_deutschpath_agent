from __future__ import annotations

from functools import lru_cache
from importlib.metadata import version
from pathlib import Path
from threading import Lock
from typing import Any

from PIL import Image
from rapidocr import RapidOCR


ENGINE_NAME = "RapidOCR"
ENGINE_VERSION = version("rapidocr")
MODEL_NAME = "PP-OCRv6 multilingual small (ONNX Runtime CPU)"
_ENGINE_LOCK = Lock()
_SUPPORTED_LANGUAGES = {"en": "en", "de": "de"}


def _local_model_directory() -> Path:
    import rapidocr

    return Path(rapidocr.__file__).resolve().parent / "models"


@lru_cache(maxsize=1)
def _get_engine(language: str):
    if language not in _SUPPORTED_LANGUAGES:
        raise ValueError("language must be 'en' or 'de'")
    model_dir = _local_model_directory()
    # RapidOCR downloads missing models during construction. Refuse to start OCR
    # unless both expected package-bundled files already exist, keeping this
    # stdio tool offline and reproducible at runtime.
    required = (model_dir / "PP-OCRv6_det_small.onnx", model_dir / "PP-OCRv6_rec_small.onnx")
    if not all(path.is_file() for path in required):
        raise RuntimeError("bundled PP-OCRv6 models are missing; install the pinned OCR dependency")
    return RapidOCR(
        params={
            "Det.lang_type": _SUPPORTED_LANGUAGES[language],
            "Rec.lang_type": _SUPPORTED_LANGUAGES[language],
            "Global.model_root_dir": str(model_dir),
            "Global.use_cls": False,
            "Global.log_level": "error",
            "EngineConfig.onnxruntime.intra_op_num_threads": 2,
            "EngineConfig.onnxruntime.inter_op_num_threads": 1,
        }
    )


def _group_lines(items: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    if not items:
        return []
    items.sort(key=lambda item: (item["bbox"][1], item["bbox"][0]))
    heights = [max(1.0, item["bbox"][3] - item["bbox"][1]) for item in items]
    line_tolerance = max(8.0, sorted(heights)[len(heights) // 2] * 0.65)
    groups: list[list[dict[str, Any]]] = []
    centers: list[float] = []
    for item in items:
        center = (item["bbox"][1] + item["bbox"][3]) / 2
        match = next((i for i, known in enumerate(centers) if abs(center - known) <= line_tolerance), None)
        if match is None:
            groups.append([item])
            centers.append(center)
        else:
            groups[match].append(item)
            centers[match] = sum((x["bbox"][1] + x["bbox"][3]) / 2 for x in groups[match]) / len(groups[match])
    return [sorted(group, key=lambda item: item["bbox"][0]) for group in sorted(groups, key=lambda group: min(x["bbox"][1] for x in group))]


def _table_candidates(lines: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    multi = [line for line in lines if len(line) >= 2]
    if len(multi) < 2:
        return []
    rows = [
        [
            {"text": item["text"], "confidence": item["confidence"], "bbox": item["bbox"]}
            for item in line
        ]
        for line in multi
    ]
    return [{"kind": "layout_candidate", "rows": rows}]


def extract_text(image: Image.Image, language: str) -> dict[str, Any]:
    with _ENGINE_LOCK:
        engine = _get_engine(language)
        result = engine(image)
    texts = list(result.txts) if result.txts is not None else []
    boxes = list(result.boxes) if result.boxes is not None else []
    scores = list(result.scores) if result.scores is not None else []
    items = []
    for text, box, score in zip(texts, boxes, scores):
        coords = [[float(point[0]), float(point[1])] for point in box]
        xs = [point[0] for point in coords]
        ys = [point[1] for point in coords]
        items.append({"text": str(text), "confidence": float(score), "polygon": coords,
                      "bbox": [min(xs), min(ys), max(xs), max(ys)]})
    lines = _group_lines(items)
    line_results = [
        {
            "text": " ".join(item["text"] for item in line),
            "confidence": sum(item["confidence"] for item in line) / len(line),
            "bbox": [
                min(item["bbox"][0] for item in line), min(item["bbox"][1] for item in line),
                max(item["bbox"][2] for item in line), max(item["bbox"][3] for item in line),
            ],
            "words": [{"text": item["text"], "confidence": item["confidence"], "polygon": item["polygon"]} for item in line],
        }
        for line in lines
    ]
    warnings = []
    if not texts:
        warnings.append("no_text_detected")
    tables = _table_candidates(lines)
    if tables:
        warnings.append("table_cells_are_layout_candidates_and_require_human_review")
    return {
        "success": bool(texts),
        "status": "ok" if texts else "no_text_detected",
        "engine": ENGINE_NAME,
        "engine_version": ENGINE_VERSION,
        "model": MODEL_NAME,
        "language": language,
        "raw_text": "\n".join(item["text"] for item in line_results),
        "lines": line_results,
        "tables": tables,
        "warnings": warnings,
    }
