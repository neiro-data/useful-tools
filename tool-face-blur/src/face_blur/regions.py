"""Rectangular/elliptical image regions."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Literal, cast, get_args

Shape = Literal["ellipse", "rect"]
Source = Literal["auto", "manual"]

SHAPES: tuple[str, ...] = get_args(Shape)
SOURCES: tuple[str, ...] = get_args(Source)


@dataclass(frozen=True)
class Region:
    """A box in pixel coordinates (top-left origin) with a blur shape."""

    x: int
    y: int
    w: int
    h: int
    shape: Shape = "ellipse"
    score: float | None = None
    source: Source = "manual"

    def __post_init__(self) -> None:
        if self.w <= 0 or self.h <= 0:
            raise ValueError(f"Region size must be positive, got {self.w}x{self.h}")
        if self.shape not in SHAPES:
            raise ValueError(f"Invalid shape: {self.shape!r}")
        if self.source not in SOURCES:
            raise ValueError(f"Invalid source: {self.source!r}")

    def pad(self, fraction: float) -> Region:
        """Grow each side by ``fraction`` of the box size (not clamped)."""
        if fraction < 0:
            raise ValueError("Padding fraction must be >= 0")
        dx = round(self.w * fraction)
        dy = round(self.h * fraction)
        return replace(self, x=self.x - dx, y=self.y - dy, w=self.w + 2 * dx, h=self.h + 2 * dy)

    def clamp(self, width: int, height: int) -> Region | None:
        """Intersect with the image bounds; ``None`` if nothing remains."""
        x0, y0 = max(self.x, 0), max(self.y, 0)
        x1, y1 = min(self.x + self.w, width), min(self.y + self.h, height)
        if x1 <= x0 or y1 <= y0:
            return None
        return replace(self, x=x0, y=y0, w=x1 - x0, h=y1 - y0)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-friendly dict."""
        return {
            "x": self.x,
            "y": self.y,
            "w": self.w,
            "h": self.h,
            "shape": self.shape,
            "score": self.score,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: object) -> Region:
        """Build a region from a dict, raising ``ValueError`` on bad input."""
        if not isinstance(data, dict):
            raise ValueError("Region must be an object")
        try:
            coords = [data[k] for k in ("x", "y", "w", "h")]
        except KeyError as exc:
            raise ValueError(f"Region missing key: {exc.args[0]}") from exc
        for value in coords:
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise ValueError("Region coordinates must be numbers")
        try:
            x, y, w, h = (round(v) for v in coords)
        except (OverflowError, ValueError) as exc:
            raise ValueError("Region coordinates must be finite numbers") from exc
        score = data.get("score")
        if score is not None and (isinstance(score, bool) or not isinstance(score, int | float)):
            raise ValueError("Region score must be a number or null")
        return cls(
            x=x,
            y=y,
            w=w,
            h=h,
            shape=cast(Shape, data.get("shape", "ellipse")),
            score=None if score is None else float(score),
            source=cast(Source, data.get("source", "manual")),
        )
