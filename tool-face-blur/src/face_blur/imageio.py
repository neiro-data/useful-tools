"""Image decode/encode. Encoding never writes metadata (privacy)."""

from __future__ import annotations

import io
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_PIXELS = 40_000_000
INPUT_FORMATS = {"JPEG", "PNG", "WEBP"}

OutFormat = Literal["png", "jpeg", "webp"]
MIME: dict[str, str] = {"png": "image/png", "jpeg": "image/jpeg", "webp": "image/webp"}
EXT: dict[str, str] = {"png": "png", "jpeg": "jpg", "webp": "webp"}


class ImageError(ValueError):
    """The input is not a supported or safely decodable image."""


def load_bytes(data: bytes) -> NDArray[np.uint8]:
    """Decode bytes to an EXIF-corrected RGB array."""
    try:
        with Image.open(io.BytesIO(data)) as img:
            if img.format not in INPUT_FORMATS:
                raise ImageError(f"Unsupported image format: {img.format}")
            if img.width * img.height > MAX_PIXELS:
                raise ImageError(f"Image exceeds {MAX_PIXELS // 1_000_000} MP limit")
            fixed = ImageOps.exif_transpose(img)
            return np.asarray(fixed.convert("RGB"), dtype=np.uint8).copy()
    except ImageError:
        raise
    except (
        UnidentifiedImageError,
        Image.DecompressionBombError,
        SyntaxError,
        ValueError,
        OSError,
    ) as exc:
        raise ImageError(f"Cannot decode image: {exc}") from exc


def encode(rgb: NDArray[np.uint8], fmt: str = "png", quality: int = 92) -> bytes:
    """Encode an RGB array without any metadata."""
    if fmt not in MIME:
        raise ValueError(f"Invalid format: {fmt!r}")
    if not 1 <= quality <= 100:
        raise ValueError("quality must be between 1 and 100")
    buf = io.BytesIO()
    img = Image.fromarray(rgb, "RGB")
    if fmt == "png":
        img.save(buf, "PNG")
    else:
        img.save(buf, fmt.upper(), quality=quality)
    return buf.getvalue()
