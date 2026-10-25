"""YuNet face detector (OpenCV ``FaceDetectorYN``) using the bundled ONNX model."""

from __future__ import annotations

import threading
from functools import lru_cache
from importlib import resources
from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray

from .regions import Region

MODEL_NAME = "face_detection_yunet_2023mar.onnx"


class ModelNotFoundError(FileNotFoundError):
    """The YuNet model file is missing."""


def default_model_path() -> Path:
    """Path of the model shipped inside the package."""
    return Path(str(resources.files("face_blur").joinpath("models", MODEL_NAME)))


class FaceDetector:
    """Detects faces; large images are downscaled for inference only."""

    def __init__(
        self,
        model_path: str | Path,
        score_threshold: float = 0.6,
        nms: float = 0.3,
        max_side: int = 1280,
    ) -> None:
        path = Path(model_path)
        if not path.is_file():
            raise ModelNotFoundError(f"YuNet model not found at {path}")
        if max_side <= 0:
            raise ValueError("max_side must be > 0")
        self.score_threshold = score_threshold
        self.max_side = max_side
        self._lock = threading.Lock()
        self._net = cv2.FaceDetectorYN.create(str(path), "", (320, 320), score_threshold, nms, 5000)

    def detect(
        self,
        rgb: NDArray[np.uint8],
        min_score: float | None = None,
        max_side: int | None = None,
    ) -> list[Region]:
        """Return face regions in the original pixel space, clamped to the image."""
        height, width = rgb.shape[:2]
        if max_side is not None and max_side <= 0:
            raise ValueError("max_side must be > 0")
        limit = max_side or self.max_side
        scale = min(1.0, limit / max(height, width))
        bgr = np.ascontiguousarray(rgb[..., ::-1])
        if scale < 1.0:
            sw, sh = max(1, round(width * scale)), max(1, round(height * scale))
            bgr = np.asarray(
                cv2.resize(bgr, (sw, sh), interpolation=cv2.INTER_AREA), dtype=np.uint8
            )
        else:
            sw, sh = width, height
        with self._lock:
            self._net.setInputSize((sw, sh))
            self._net.setScoreThreshold(self.score_threshold if min_score is None else min_score)
            _, faces = self._net.detect(bgr)
        if faces is None:
            return []
        regions: list[Region] = []
        for row in faces:
            x, y, w, h = (float(v) / scale for v in row[:4])
            x0, y0 = max(0, round(x)), max(0, round(y))
            x1, y1 = min(width, round(x + w)), min(height, round(y + h))
            if x1 <= x0 or y1 <= y0:
                continue
            regions.append(Region(x0, y0, x1 - x0, y1 - y0, "ellipse", float(row[14]), "auto"))
        regions.sort(key=lambda r: (r.y, r.x))
        return regions


@lru_cache(maxsize=1)
def get_detector() -> FaceDetector:
    """Lazy singleton detector using the bundled model."""
    return FaceDetector(default_model_path())
