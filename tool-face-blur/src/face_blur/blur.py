"""Pure numpy/cv2 region blurring (no IO)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal, get_args

import cv2
import numpy as np
from numpy.typing import NDArray

from .regions import Region

Method = Literal["gaussian", "pixelate", "solid"]
METHODS: tuple[str, ...] = get_args(Method)

Image = NDArray[np.uint8]


def _blur_roi(roi: Image, method: str, strength: int, w: int, h: int) -> Image:
    size = max(w, h)
    if method == "gaussian":
        sigma = max(1.0, size * 0.04 * strength)
        return np.asarray(
            cv2.GaussianBlur(roi, (0, 0), sigma, borderType=cv2.BORDER_REFLECT), dtype=np.uint8
        )
    if method == "pixelate":
        block = max(2, round(size * strength / 40))
        rh, rw = roi.shape[:2]
        small = cv2.resize(
            roi,
            (max(1, rw // block), max(1, rh // block)),
            interpolation=cv2.INTER_AREA,
        )
        return np.asarray(
            cv2.resize(small, (rw, rh), interpolation=cv2.INTER_NEAREST), dtype=np.uint8
        )
    # solid: flat fill with the mean colour of the box
    mean = roi.reshape(-1, roi.shape[-1]).mean(axis=0)
    out = np.empty_like(roi)
    out[:] = np.round(mean).astype(np.uint8)
    return out


def apply(
    rgb: Image,
    regions: Sequence[Region],
    method: str = "gaussian",
    strength: int = 5,
    feather: float = 0.05,
) -> Image:
    """Return a copy of ``rgb`` with ``regions`` blurred.

    Kernel/block sizes scale with each box so all faces get the same visual strength.
    ``feather`` is the soft mask edge as a fraction of the box size.
    """
    if method not in METHODS:
        raise ValueError(f"Invalid method: {method!r}")
    if not 1 <= strength <= 10:
        raise ValueError("strength must be between 1 and 10")
    if feather < 0:
        raise ValueError("feather must be >= 0")
    if rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError("Expected an RGB image of shape (H, W, 3)")

    out = rgb.copy()
    img_h, img_w = rgb.shape[:2]
    for region in regions:
        margin = round(max(region.w, region.h) * feather)
        ex0, ey0 = max(region.x - margin, 0), max(region.y - margin, 0)
        ex1 = min(region.x + region.w + margin, img_w)
        ey1 = min(region.y + region.h + margin, img_h)
        if ex1 <= ex0 or ey1 <= ey0:
            continue
        # Source is read from the progressively edited image so overlaps stay blurred.
        roi = np.ascontiguousarray(out[ey0:ey1, ex0:ex1])
        blurred = _blur_roi(roi, method, strength, region.w, region.h)

        mask = np.zeros(roi.shape[:2], dtype=np.uint8)
        left, top = region.x - ex0, region.y - ey0
        if region.shape == "ellipse":
            center = (left + region.w // 2, top + region.h // 2)
            cv2.ellipse(mask, center, (region.w // 2, region.h // 2), 0, 0, 360, 255, cv2.FILLED)
        else:
            cv2.rectangle(
                mask, (left, top), (left + region.w - 1, top + region.h - 1), 255, cv2.FILLED
            )
        if margin > 0:
            mask = np.asarray(
                cv2.GaussianBlur(
                    mask, (0, 0), max(0.5, margin / 2), borderType=cv2.BORDER_REPLICATE
                ),
                dtype=np.uint8,
            )
        alpha = (mask.astype(np.float32) / 255.0)[..., None]
        mixed = roi.astype(np.float32) * (1 - alpha) + blurred.astype(np.float32) * alpha
        out[ey0:ey1, ex0:ex1] = np.clip(np.round(mixed), 0, 255).astype(np.uint8)
    return out
