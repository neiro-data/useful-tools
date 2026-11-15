from __future__ import annotations

import pytest

from face_blur.regions import Region


def test_pad_grows_each_side() -> None:
    r = Region(50, 50, 100, 40).pad(0.1)
    assert (r.x, r.y, r.w, r.h) == (40, 46, 120, 48)


def test_clamp_at_edges() -> None:
    r = Region(-10, -5, 50, 50).clamp(100, 100)
    assert r is not None
    assert (r.x, r.y, r.w, r.h) == (0, 0, 40, 45)
    r2 = Region(90, 90, 50, 50).clamp(100, 100)
    assert r2 is not None
    assert (r2.x, r2.y, r2.w, r2.h) == (90, 90, 10, 10)


def test_clamp_fully_outside() -> None:
    assert Region(200, 200, 10, 10).clamp(100, 100) is None


@pytest.mark.parametrize("w,h", [(0, 5), (5, 0), (-3, 5), (5, -3)])
def test_invalid_sizes(w: int, h: int) -> None:
    with pytest.raises(ValueError):
        Region(0, 0, w, h)


def test_invalid_shape_and_source() -> None:
    with pytest.raises(ValueError):
        Region(0, 0, 5, 5, shape="star")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        Region(0, 0, 5, 5, source="x")  # type: ignore[arg-type]


def test_negative_padding() -> None:
    with pytest.raises(ValueError):
        Region(0, 0, 5, 5).pad(-0.1)


def test_dict_round_trip() -> None:
    r = Region(1, 2, 3, 4, "rect", 0.9, "auto")
    assert Region.from_dict(r.to_dict()) == r


def test_from_dict_defaults_and_errors() -> None:
    r = Region.from_dict({"x": 1.4, "y": 2, "w": 3, "h": 4})
    assert r.shape == "ellipse" and r.score is None and r.x == 1
    for bad in (
        "nope",
        {"x": 1},
        {"x": "a", "y": 0, "w": 1, "h": 1},
        {"x": 0, "y": 0, "w": 0, "h": 1},
    ):
        with pytest.raises(ValueError):
            Region.from_dict(bad)
    with pytest.raises(ValueError):
        Region.from_dict({"x": 0, "y": 0, "w": 1, "h": 1, "score": "hi"})


@pytest.mark.parametrize("bad", [float("inf"), float("-inf"), float("nan")])
def test_from_dict_non_finite(bad: float) -> None:
    with pytest.raises(ValueError):
        Region.from_dict({"x": bad, "y": 0, "w": 5, "h": 5})
