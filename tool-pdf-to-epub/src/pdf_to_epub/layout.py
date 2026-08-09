"""Column and zone layout detection. Pure, stdlib-only."""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass, field

from pdf_to_epub.config import Thresholds
from pdf_to_epub.models import Warning
from pdf_to_epub.pdf_source import Word


@dataclass(frozen=True)
class Gutter:
    x0: float
    x1: float


@dataclass(frozen=True)
class Zone:
    bbox: tuple[float, float, float, float]
    column_idx: int
    band_idx: int
    words: tuple[Word, ...]


@dataclass(frozen=True)
class ColumnResult:
    gutters: tuple[Gutter, ...]
    warnings: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PageLayout:
    zones: tuple[Zone, ...]
    gutters: tuple[Gutter, ...]
    orphan_word_frac: float
    warnings: tuple[Warning, ...] = field(default_factory=tuple)


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = int(round(pct / 100.0 * (len(ordered) - 1)))
    idx = max(0, min(idx, len(ordered) - 1))
    return ordered[idx]


def detect_columns(
    words: Sequence[Word], width: float, height: float, t: Thresholds
) -> ColumnResult:
    """Detect vertical column gutters, validated by cross-strip persistence."""
    if not words or width <= 0:
        return ColumnResult(gutters=())

    xs0 = [w.x0 for w in words]
    xs1 = [w.x1 for w in words]
    ys0 = [w.y0 for w in words]
    ys1 = [w.y1 for w in words]
    lo_x = _percentile(xs0, 2)
    hi_x = _percentile(xs1, 98)
    lo_y = _percentile(ys0, 2)
    hi_y = _percentile(ys1, 98)

    trimmed = [w for w in words if lo_x <= w.x0 and w.x1 <= hi_x and lo_y <= w.y0 and w.y1 <= hi_y]
    if not trimmed:
        return ColumnResult(gutters=())

    bin_w = t.gutter_bin_pt
    n_bins = max(1, int(width / bin_w) + 1)

    # Split the page into horizontal strips, keeping only the populated ones, and
    # compute per-bin coverage within each strip separately.
    strip_h = height / t.persistence_strips if height > 0 else 0.0
    strips: list[list[Word]] = [[] for _ in range(t.persistence_strips)]
    if strip_h > 0:
        for w in trimmed:
            cy = (w.y0 + w.y1) / 2
            idx = min(t.persistence_strips - 1, max(0, int(cy / strip_h)))
            strips[idx].append(w)
    populated_strips = [s for s in strips if s]
    if not populated_strips:
        return ColumnResult(gutters=())

    empty_strip_count = [0] * n_bins
    for strip_words in populated_strips:
        strip_coverage = [False] * n_bins
        for w in strip_words:
            first = max(0, int(w.x0 / bin_w))
            last = min(n_bins - 1, int(w.x1 / bin_w))
            for b in range(first, last + 1):
                strip_coverage[b] = True
        for b in range(n_bins):
            if not strip_coverage[b]:
                empty_strip_count[b] += 1

    # A bin qualifies as a gutter bin if it is word-free in enough populated strips.
    gutter_bin = [
        (empty_strip_count[b] / len(populated_strips)) >= t.persistence_min_frac
        for b in range(n_bins)
    ]

    # Find maximal runs of gutter bins.
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for i, is_gutter in enumerate(gutter_bin):
        if is_gutter and start is None:
            start = i
        elif not is_gutter and start is not None:
            runs.append((start, i - 1))
            start = None
    if start is not None:
        runs.append((start, n_bins - 1))

    validated: list[Gutter] = []
    for start_bin, end_bin in runs:
        x0 = start_bin * bin_w
        x1 = min((end_bin + 1) * bin_w, width)
        run_width = x1 - x0
        if run_width < t.gutter_min_width_frac * width:
            continue
        centre_frac = ((x0 + x1) / 2) / width
        if not (t.gutter_search_lo <= centre_frac <= t.gutter_search_hi):
            continue
        validated.append(Gutter(x0=x0, x1=x1))

    if not validated:
        return ColumnResult(gutters=())

    validated.sort(key=lambda g: g.x0)

    if len(validated) > t.max_gutters:
        return ColumnResult(gutters=(), warnings=("layout.ambiguous_columns",))

    # Verify each resulting column holds a minimum fraction of words.
    boundaries = [0.0, *[g for pair in validated for g in (pair.x0, pair.x1)], width]
    col_edges: list[float] = [0.0]
    for g in validated:
        col_edges.append((g.x0 + g.x1) / 2)
    col_edges.append(width)
    del boundaries

    total = len(trimmed)
    for i in range(len(col_edges) - 1):
        lo, hi = col_edges[i], col_edges[i + 1]
        count = sum(1 for w in trimmed if lo <= (w.x0 + w.x1) / 2 < hi)
        if total and count / total < t.column_min_word_frac:
            return ColumnResult(gutters=())

    return ColumnResult(gutters=tuple(validated))


def _clusters(words: Sequence[Word]) -> list[tuple[float, float, tuple[Word, ...]]]:
    """Group words into visually contiguous line runs for spanning-zone detection.

    Words sharing a y-band are only merged into one cluster while horizontally
    contiguous; a large x-gap (e.g. crossing an empty gutter) starts a new cluster,
    so two side-by-side column lines at the same y are not mistaken for one
    column-spanning line.
    """
    sorted_words = sorted(words, key=lambda w: (round(w.y0, 1), w.x0))
    rows: list[list[Word]] = []
    for w in sorted_words:
        placed = False
        for row in rows:
            last = row[-1]
            if abs(w.y0 - last.y0) <= max(1.0, (w.y1 - w.y0) * 0.5):
                row.append(w)
                placed = True
                break
        if not placed:
            rows.append([w])

    result: list[tuple[float, float, tuple[Word, ...]]] = []
    for row in rows:
        row.sort(key=lambda w: w.x0)
        gaps = [row[i + 1].x0 - row[i].x1 for i in range(len(row) - 1)]
        normal_gap = statistics.median(gaps) if gaps else 0.0
        split_threshold = max(3.0 * normal_gap, 12.0)

        run: list[Word] = [row[0]]
        for i in range(1, len(row)):
            gap = row[i].x0 - row[i - 1].x1
            if gap > split_threshold:
                y0 = min(w.y0 for w in run)
                y1 = max(w.y1 for w in run)
                result.append((y0, y1, tuple(run)))
                run = []
            run.append(row[i])
        y0 = min(w.y0 for w in run)
        y1 = max(w.y1 for w in run)
        result.append((y0, y1, tuple(run)))
    return result


def segment_zones(
    words: Sequence[Word],
    gutters: Sequence[Gutter],
    width: float,
    height: float,
    t: Thresholds,
    column_warnings: Sequence[str] = (),
) -> PageLayout:
    """Segment a page into reading-order zones given already-detected gutters."""
    warnings: list[Warning] = [
        Warning(code=code, message=code, page=None, severity="warning") for code in column_warnings
    ]

    if not gutters:
        band_bbox = (0.0, 0.0, width, height)
        zone = Zone(bbox=band_bbox, column_idx=0, band_idx=0, words=tuple(words))
        return PageLayout(
            zones=(zone,), gutters=(), orphan_word_frac=0.0, warnings=tuple(warnings)
        )

    line_clusters = _clusters(words)

    spanning_y: list[tuple[float, float]] = []
    for y0, y1, cluster in line_clusters:
        cx0 = min(w.x0 for w in cluster)
        cx1 = max(w.x1 for w in cluster)
        spans_all = True
        for gutter in gutters:
            gw = gutter.x1 - gutter.x0
            reaches_left = cx0 <= gutter.x0 + t.spanning_overlap_frac * gw
            reaches_right = cx1 >= gutter.x1 - t.spanning_overlap_frac * gw
            if not (reaches_left and reaches_right):
                spans_all = False
                break
        if spans_all:
            spanning_y.append((y0, y1))

    spanning_y.sort()
    band_edges = [0.0]
    for y0, y1 in spanning_y:
        band_edges.append(y0)
        band_edges.append(y1)
    band_edges.append(height)
    band_edges = sorted(set(band_edges))

    col_edges: list[float] = [0.0]
    for g in gutters:
        col_edges.append((g.x0 + g.x1) / 2)
    col_edges.append(width)

    zones: list[Zone] = []
    assigned: set[int] = set()
    band_idx = 0
    for i in range(len(band_edges) - 1):
        by0, by1 = band_edges[i], band_edges[i + 1]
        if by1 - by0 <= 1e-6:
            continue
        band_words = [w for w in words if by0 - 0.5 <= (w.y0 + w.y1) / 2 < by1 + 0.5]
        if not band_words:
            continue

        is_spanning_band = any(
            abs(by0 - sy0) < 1e-6 and abs(by1 - sy1) < 1e-6 for sy0, sy1 in spanning_y
        )
        if is_spanning_band:
            zone_words = tuple(band_words)
            zones.append(
                Zone(bbox=(0.0, by0, width, by1), column_idx=0, band_idx=band_idx, words=zone_words)
            )
            for w in zone_words:
                assigned.add(id(w))
        else:
            for col in range(len(col_edges) - 1):
                clo, chi = col_edges[col], col_edges[col + 1]
                col_words = tuple(w for w in band_words if clo <= (w.x0 + w.x1) / 2 < chi)
                if not col_words:
                    continue
                zones.append(
                    Zone(
                        bbox=(clo, by0, chi, by1),
                        column_idx=col,
                        band_idx=band_idx,
                        words=col_words,
                    )
                )
                for w in col_words:
                    assigned.add(id(w))
        band_idx += 1

    total = len(words)
    orphan = sum(1 for w in words if id(w) not in assigned)
    orphan_frac = orphan / total if total else 0.0

    return PageLayout(
        zones=tuple(zones),
        gutters=tuple(gutters),
        orphan_word_frac=orphan_frac,
        warnings=tuple(warnings),
    )
