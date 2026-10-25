from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from face_blur import imageio


def test_rotated_fixture_has_exif_and_decodes_upright(
    face_path: Path, face_rotated_path: Path
) -> None:
    with Image.open(face_rotated_path) as raw:
        assert raw.getexif().get(0x0112) == 6
        stored = raw.size
    upright = imageio.load_bytes(face_rotated_path.read_bytes())
    plain = imageio.load_bytes(face_path.read_bytes())
    assert upright.shape[:2] == (stored[0], stored[1])  # swapped: H=stored W, W=stored H
    assert upright.shape == plain.shape


@pytest.mark.parametrize("fmt", ["png", "jpeg", "webp"])
def test_encode_has_no_exif(face_rotated_path: Path, fmt: str) -> None:
    rgb = imageio.load_bytes(face_rotated_path.read_bytes())
    data = imageio.encode(rgb, fmt, 80)
    with Image.open(io.BytesIO(data)) as out:
        assert len(out.getexif()) == 0
        assert out.size == (rgb.shape[1], rgb.shape[0])
        assert "exif" not in out.info


def test_non_image_raises() -> None:
    with pytest.raises(imageio.ImageError):
        imageio.load_bytes(b"not an image at all")


def test_unsupported_format_raises() -> None:
    buf = io.BytesIO()
    Image.new("RGB", (4, 4)).save(buf, "GIF")
    with pytest.raises(imageio.ImageError):
        imageio.load_bytes(buf.getvalue())


def test_pixel_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    buf = io.BytesIO()
    Image.new("RGB", (10, 10)).save(buf, "PNG")
    monkeypatch.setattr(imageio, "MAX_PIXELS", 50)
    with pytest.raises(imageio.ImageError):
        imageio.load_bytes(buf.getvalue())


def test_encode_validation() -> None:
    rgb = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        imageio.encode(rgb, "bmp")
    with pytest.raises(ValueError):
        imageio.encode(rgb, "jpeg", 0)


def test_pillow_syntax_error_maps_to_image_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: object, **_k: object) -> None:
        raise SyntaxError("broken png")

    monkeypatch.setattr(Image, "open", boom)
    with pytest.raises(imageio.ImageError):
        imageio.load_bytes(b"x")
