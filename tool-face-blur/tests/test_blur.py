from __future__ import annotations

import numpy as np
import pytest
from numpy.typing import NDArray

from face_blur import blur
from face_blur.regions import Region

U8 = NDArray[np.uint8]
BOX = Region(40, 30, 80, 60, "rect")


def _var(img: U8, r: Region) -> float:
    return float(img[r.y : r.y + r.h, r.x : r.x + r.w].astype(np.float64).var())


@pytest.mark.parametrize("method", ["gaussian", "pixelate", "solid"])
def test_variance_drops_and_outside_untouched(noise: U8, method: str) -> None:
    out = blur.apply(noise, [BOX], method, 5, feather=0.0)
    assert _var(out, BOX) < _var(noise, BOX) * 0.5
    mask = np.ones(noise.shape[:2], dtype=bool)
    mask[BOX.y : BOX.y + BOX.h, BOX.x : BOX.x + BOX.w] = False
    assert np.array_equal(out[mask], noise[mask])


def test_feather_stays_near_box(noise: U8) -> None:
    out = blur.apply(noise, [BOX], "solid", 5, feather=0.05)
    assert np.array_equal(out[:20], noise[:20])


def test_ellipse_corners_nearly_untouched(noise: U8) -> None:
    r = Region(40, 30, 80, 60, "ellipse")
    out = blur.apply(noise, [r], "solid", 5, feather=0.0)
    corner = (slice(30, 34), slice(40, 44))
    assert np.array_equal(out[corner], noise[corner])
    centre = out[55:65, 75:85]
    assert centre.std() < 1.0


def test_solid_is_uniform(noise: U8) -> None:
    out = blur.apply(noise, [BOX], "solid", 5, feather=0.0)
    inner = out[BOX.y : BOX.y + BOX.h, BOX.x : BOX.x + BOX.w]
    assert (inner == inner[0, 0]).all()


def test_higher_strength_lowers_variance(noise: U8) -> None:
    low = blur.apply(noise, [BOX], "gaussian", 1)
    high = blur.apply(noise, [BOX], "gaussian", 9)
    assert _var(high, BOX) < _var(low, BOX)


def test_edge_and_outside_regions_do_not_crash(noise: U8) -> None:
    edge = Region(140, 100, 60, 60, "ellipse")
    out = blur.apply(noise, [edge, Region(-50, -50, 30, 30), Region(500, 500, 10, 10)])
    assert out.shape == noise.shape
    assert _var(out, Region(140, 100, 20, 20)) < _var(noise, Region(140, 100, 20, 20))


def test_no_regions_no_change_and_input_not_mutated(noise: U8) -> None:
    before = noise.copy()
    out = blur.apply(noise, [])
    assert np.array_equal(out, noise)
    blur.apply(noise, [BOX])
    assert np.array_equal(noise, before)


def test_validation(noise: U8) -> None:
    with pytest.raises(ValueError):
        blur.apply(noise, [BOX], "bogus")
    with pytest.raises(ValueError):
        blur.apply(noise, [BOX], "gaussian", 11)
    with pytest.raises(ValueError):
        blur.apply(noise[..., 0], [BOX])
