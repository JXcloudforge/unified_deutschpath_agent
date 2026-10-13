from __future__ import annotations

import os
import re
import stat
from pathlib import Path

from PIL import Image, UnidentifiedImageError


MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
MAX_IMAGE_SIDE = 8_000
ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP", "BMP", "TIFF"}
EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
IMAGE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")
_REPARSE_POINT = 0x0400


class ImageInputError(ValueError):
    """An image identifier or file failed the OCR input policy."""


def _is_reparse_or_link(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & _REPARSE_POINT)


def _assert_no_reparse_components(path: Path) -> None:
    # Walk from the volume root so a junction in any parent cannot redirect the input.
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    for component in absolute.parts[1:]:
        current = current / component
        if current.exists() and _is_reparse_or_link(current):
            raise ImageInputError("OCR input path contains a symlink or reparse point")


def load_authorized_image(input_dir: str | Path, image_id: str):
    """Read one host-staged image by opaque ID; never accept paths or URLs."""
    if not isinstance(image_id, str) or not IMAGE_ID.fullmatch(image_id):
        raise ImageInputError("image_id must be 1-80 ASCII letters, digits, '_' or '-'")

    root = Path(input_dir)
    if not root.is_absolute():
        raise ImageInputError("OCR_INPUT_DIR must be an absolute dedicated directory")
    _assert_no_reparse_components(root)
    if not root.is_dir():
        raise ImageInputError("OCR input directory is unavailable")
    resolved_root = Path(os.path.abspath(root))

    matches = [p for p in root.iterdir() if p.stem == image_id and p.suffix.lower() in EXTENSIONS]
    if len(matches) != 1:
        raise ImageInputError("image_id is missing or ambiguous in the OCR input directory")
    candidate = matches[0]
    _assert_no_reparse_components(candidate)
    try:
        resolved = Path(os.path.abspath(candidate))
        resolved.relative_to(resolved_root)
    except (OSError, ValueError) as exc:
        raise ImageInputError("image is outside the OCR input directory") from exc
    if not candidate.is_file():
        raise ImageInputError("OCR input is not a regular image file")

    try:
        if candidate.stat().st_size > MAX_IMAGE_BYTES:
            raise ImageInputError("image exceeds the 10 MiB size limit")
        # The file is opened only after path/reparse checks; read at most limit+1 bytes.
        with candidate.open("rb") as stream:
            raw = stream.read(MAX_IMAGE_BYTES + 1)
    except OSError as exc:
        raise ImageInputError("OCR image could not be read") from exc
    if not raw:
        raise ImageInputError("OCR image is empty")
    if len(raw) > MAX_IMAGE_BYTES:
        raise ImageInputError("image exceeds the 10 MiB size limit")

    try:
        from io import BytesIO

        with Image.open(BytesIO(raw)) as probe:
            actual_format = probe.format
            width, height = probe.size
            if actual_format not in ALLOWED_FORMATS:
                raise ImageInputError("image content must be PNG, JPEG, WEBP, BMP or TIFF")
            if candidate.suffix.lower() not in _format_extensions(actual_format):
                raise ImageInputError("image content does not match its file extension")
            if width <= 0 or height <= 0 or width > MAX_IMAGE_SIDE or height > MAX_IMAGE_SIDE:
                raise ImageInputError("image dimensions exceed the 8000-pixel side limit")
            if width * height > MAX_IMAGE_PIXELS:
                raise ImageInputError("image exceeds the 20-megapixel limit")
            probe.verify()
        with Image.open(BytesIO(raw)) as image:
            image.load()
            return image.convert("RGB"), actual_format, len(raw), raw
    except ImageInputError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise ImageInputError("image is corrupt or not a supported image") from exc


def _format_extensions(image_format: str) -> set[str]:
    return {
        "PNG": {".png"},
        "JPEG": {".jpg", ".jpeg"},
        "WEBP": {".webp"},
        "BMP": {".bmp"},
        "TIFF": {".tif", ".tiff"},
    }[image_format]
