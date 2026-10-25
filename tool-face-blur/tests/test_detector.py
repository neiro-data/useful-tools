from __future__ import annotations

import hashlib
from importlib import resources
from pathlib import Path

import numpy as np
import pytest

from face_blur import imageio
from face_blur.detector import FaceDetector, ModelNotFoundError, default_model_path

MODEL_SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"


def test_model_checksum_and_resources() -> None:
    path = default_model_path()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == MODEL_SHA256
    pkg = resources.files("face_blur")
    assert pkg.joinpath("static", "index.html").is_file()
    assert pkg.joinpath("static", "app.js").is_file()
    assert pkg.joinpath("models", "LICENSE-yunet").is_file()


def test_fixture_face_found(face_path: Path) -> None:
    rgb = imageio.load_bytes(face_path.read_bytes())
    faces = FaceDetector(default_model_path()).detect(rgb)
    assert len(faces) >= 1
    best = max(faces, key=lambda r: r.score or 0)
    cx, cy = best.x + best.w / 2, best.y + best.h / 2
    h, w = rgb.shape[:2]
    # face sits in the upper-middle part of the portrait
    assert 0.35 * w < cx < 0.85 * w
    assert 0.08 * h < cy < 0.5 * h
    assert best.source == "auto"


def test_blank_image_has_no_faces() -> None:
    blank = np.full((200, 200, 3), 128, dtype=np.uint8)
    assert FaceDetector(default_model_path()).detect(blank) == []


def test_max_side_downscale_returns_original_coords(face_path: Path) -> None:
    rgb = imageio.load_bytes(face_path.read_bytes())
    det = FaceDetector(default_model_path())
    full = det.detect(rgb)[0]
    small = det.detect(rgb, max_side=250)[0]
    h, w = rgb.shape[:2]
    assert small.x + small.w <= w and small.y + small.h <= h
    assert abs(small.x - full.x) < 0.2 * full.w
    assert abs(small.y - full.y) < 0.2 * full.h
    assert abs(small.w - full.w) < 0.3 * full.w


def test_missing_model(tmp_path: Path) -> None:
    with pytest.raises(ModelNotFoundError, match="not found"):
        FaceDetector(tmp_path / "nope.onnx")


def test_max_side_validation(face_path: Path) -> None:
    rgb = imageio.load_bytes(face_path.read_bytes())
    with pytest.raises(ValueError):
        FaceDetector(default_model_path(), max_side=0)
    with pytest.raises(ValueError):
        FaceDetector(default_model_path()).detect(rgb, max_side=-1)
