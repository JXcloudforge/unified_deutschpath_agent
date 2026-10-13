"""One-shot OCR worker. Its stdin contains validated image bytes, never a path."""

from __future__ import annotations

from io import BytesIO
import json
import sys

from PIL import Image, UnidentifiedImageError

from .engine import extract_text


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    raw = sys.stdin.buffer.read(10 * 1024 * 1024 + 1)
    if not raw or len(raw) > 10 * 1024 * 1024:
        print(json.dumps({"success": False, "status": "invalid_image", "error": "invalid image payload"}))
        return 0
    try:
        with Image.open(BytesIO(raw)) as source:
            source.load()
            result = extract_text(source.convert("RGB"), sys.argv[1])
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        print(json.dumps({"success": False, "status": "engine_error", "error": type(exc).__name__}))
        return 0
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
