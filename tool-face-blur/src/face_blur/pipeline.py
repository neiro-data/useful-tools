"""Detect-then-blur pipeline shared by the CLI and the API."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import cast

import numpy as np
from numpy.typing import NDArray

from . import blur
from .detector import get_detector
from .regions import SHAPES, Region, Shape


@dataclass(frozen=True)
class AutoOptions:
    """Options for automatic blurring."""

    method: str = "gaussian"
    strength: int = 5
    shape: str = "ellipse"
    padding: float = 0.15
    min_score: float | None = None
    max_side: int | None = None

    def __post_init__(self) -> None:
        if self.method not in blur.METHODS:
            raise ValueError(f"Invalid method: {self.method!r}")
        if not 1 <= self.strength <= 10:
            raise ValueError("strength must be between 1 and 10")
        if self.shape not in SHAPES:
            raise ValueError(f"Invalid shape: {self.shape!r}")
        if not 0 <= self.padding <= 0.5:
            raise ValueError("padding must be between 0 and 0.5")
        if self.max_side is not None and self.max_side <= 0:
            raise ValueError("max_side must be > 0")
        if self.min_score is not None and not 0 <= self.min_score <= 1:
            raise ValueError("min_score must be between 0 and 1")


def detect(
    rgb: NDArray[np.uint8], min_score: float | None = None, max_side: int | None = None
) -> list[Region]:
    """Detect faces with the shared detector."""
    return get_detector().detect(rgb, min_score=min_score, max_side=max_side)


def auto_blur(rgb: NDArray[np.uint8], opts: AutoOptions) -> tuple[NDArray[np.uint8], list[Region]]:
    """Detect all faces and blur them; returns the image and the (padded) regions used."""
    found = detect(rgb, opts.min_score, opts.max_side)
    height, width = rgb.shape[:2]
    regions: list[Region] = []
    for face in found:
        shaped = replace(face, shape=cast(Shape, opts.shape))
        clamped = shaped.pad(opts.padding).clamp(width, height)
        if clamped is not None:
            regions.append(clamped)
    return blur.apply(rgb, regions, opts.method, opts.strength), regions
