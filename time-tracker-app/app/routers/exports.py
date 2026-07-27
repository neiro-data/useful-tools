"""``/exports`` endpoints. See ``app/API_CONTRACT.md#exports`` for the full contract.

Download endpoints: a full SQLite database backup, a CSV export of completed entries, and HTML,
Markdown, and PDF reports (all built on top of ``app/routers/reports.py``'s aggregation,
``get_reports_summary``). The HTML/PDF reports visually mirror the Reports page
(``frontend/src/pages/Reports/ReportsPage.tsx``): card layout, a stacked hours-by-category chart,
and a polyline entries-per-bucket chart -- ported from ``StackedCategoryChart.tsx``/
``CountLineChart.tsx``. There is no longer an Outlook-compatibility constraint on the HTML export
(inline ``<svg>`` and a ``<style>`` block are both used), and no export renders a data table.
"""

import csv
import io
import os
import re
import sqlite3
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from html import escape

from fastapi import APIRouter
from fastapi.responses import FileResponse, Response
from fpdf import FPDF
from starlette.background import BackgroundTask

from app.deps import DbDep
from app.errors import ValidationError
from app.repo import (
    get_category_row,
    get_settings_timezone,
    get_tags_for_entry,
    local_range_bounds_utc,
)
from app.report_theme import (
    ACCENT,
    BG_SUBTLE,
    BORDER,
    FALLBACK_CAT,
    FONT_MONO,
    FONT_SANS,
    RADIUS_PX,
    SURFACE,
    TEXT,
    TEXT_MUTED,
    TEXT_SECONDARY,
    hex_to_rgb,
    resolve_category_color,
    tag_gray,
)
from app.routers.reports import build_narrative, format_minutes, get_reports_summary
from app.schemas import (
    ReportBucketCategorySplit,
    ReportDayBreakdown,
    ReportPeriod,
    ReportSummaryResponse,
)

router = APIRouter(prefix="/exports", tags=["exports"])


def _report_filename(db: sqlite3.Connection, extension: str) -> str:
    """Build a report export filename the same way ``export_entries_csv`` does: ``<label>``
    slug + generation-date stamp."""
    label = _safe_filename_slug(_get_database_label(db))
    date_stamp = datetime.now(UTC).strftime("%Y%m%d")
    return f"{label}-report-{date_stamp}.{extension}"


@dataclass(frozen=True)
class Segment:
    """One slice of a segmented breakdown bar (category or tag), mirroring
    ``SegmentedBreakdown``'s props in ``frontend/src/components/SegmentedBreakdown``."""

    label: str
    minutes: int
    percent: float
    color: str


_TAG_VISIBLE_LIMIT = 5
"""Tag legends show only the top N segments plus a "+N more tags" line, matching
``ReportsPage.tsx``'s ``<SegmentedBreakdown ... visibleLimit={5} />`` for its "By tag" section
(see ``SegmentedBreakdown.tsx``). The segmented bar itself always reflects every segment; only the
legend list is capped. Category legends are never capped, mirroring the app."""


def _segment_items(summary: ReportSummaryResponse) -> tuple[list[Segment], list[Segment]]:
    """Build the category/tag segmented-breakdown data used by all three report renderers.

    ``percent`` is computed against the section's own total (sum of that section's rows), not
    ``summary.total_minutes`` -- this mirrors ``ReportsPage.tsx``'s ``categoryBreakdown``/
    ``tagBreakdown`` ``useMemo`` blocks (~lines 128 and 140), since ``by_tag`` totals can exceed
    ``total_minutes`` (an entry with multiple tags contributes its full duration to each tag).
    """
    category_total = sum(row.total_minutes for row in summary.by_category)
    category_segments = [
        Segment(
            label=row.category.name if row.category is not None else "Uncategorized",
            minutes=row.total_minutes,
            percent=(100 * row.total_minutes / category_total) if category_total else 0.0,
            color=resolve_category_color(row.category.color if row.category is not None else None),
        )
        for row in summary.by_category
    ]

    tag_total = sum(row.total_minutes for row in summary.by_tag)
    tag_segments = [
        Segment(
            label=f"#{row.tag.name}",
            minutes=row.total_minutes,
            percent=(100 * row.total_minutes / tag_total) if tag_total else 0.0,
            color=tag_gray(index),
        )
        for index, row in enumerate(summary.by_tag)
    ]

    return category_segments, tag_segments


@dataclass(frozen=True)
class CategoryLegendItem:
    """One legend entry for the "hours by category" stacked chart, mirroring
    ``StackedCategoryLegendItem`` in ``StackedCategoryChart.tsx``. Order matches
    ``summary.by_category`` (total minutes descending) -- that order is both the legend's display
    order and every bucket's stacking order."""

    category_id: int | None
    name: str
    color: str


@dataclass(frozen=True)
class StackedBucket:
    """One day/week bucket for the "hours by category" chart: its total and non-zero category
    segments, ordered to match :func:`_category_legend`'s legend order.

    ``label`` is the short axis label (e.g. ``Mon`` or ``CW 27``); ``title``, when set, is the
    full date range an abbreviated ``label`` doesn't spell out on its own (e.g. ``Jul 7 - 13``
    for ``CW 27``) -- see :func:`_bucket_labels`."""

    label: str
    title: str | None
    total_minutes: int
    segments: list[tuple[int | None, int]]


@dataclass(frozen=True)
class CountPoint:
    """One point of the "entries per day/week" chart -- same ``label``/``title`` convention as
    :class:`StackedBucket`, sharing the same buckets via :func:`_bucket_labels`."""

    label: str
    title: str | None
    count: int


def _format_weekday_short(value: date) -> str:
    """e.g. ``Mon`` -- port of ``formatWeekdayShort`` in ``frontend/src/utils/dateRange.ts``."""
    return value.strftime("%a")


def _format_short_date(value: date) -> str:
    """e.g. ``Jul 7`` -- port of ``formatShortDate`` in ``frontend/src/utils/dateRange.ts``."""
    return f"{value.strftime('%b')} {value.day}"


def _calendar_week_label(week_start: date, week_end: date) -> str:
    """e.g. ``CW 27`` -- port of ``calendarWeekLabelFor`` in
    ``frontend/src/components/MiniBarChart/bars.ts``.

    ``week_start``/``week_end`` follow ``settings.week_starts_on``, which may be Sunday-start,
    while ISO week numbers are always Monday-based: numbering directly from ``week_start`` would
    be off-by-one for a Sunday-start bucket (that Sunday belongs, per the Monday-based ISO
    definition, to the *previous* ISO week). ISO weeks are defined as belonging to the year/number
    containing their Thursday, so this scans ``[week_start, week_end]`` for a Thursday and numbers
    the bucket from that day instead -- correct regardless of which day the bucket starts on. A
    heavily clipped edge bucket (a quarter's partial first/last week) may contain no Thursday, in
    which case this falls back to ``week_start`` itself.
    """
    thursday = week_start
    cursor = week_start
    while cursor <= week_end:
        if cursor.weekday() == 3:  # Monday=0, ..., Thursday=3 (date.weekday())
            thursday = cursor
            break
        cursor += timedelta(days=1)
    return f"CW {thursday.isocalendar().week:02d}"


def _format_week_range_short(week_start: date, week_end: date) -> str:
    """e.g. ``Jul 7 - 13`` or ``Jul 28 - Aug 3`` -- port of ``formatWeekRangeShort`` in
    ``frontend/src/components/MiniBarChart/bars.ts``, used as the tooltip/full-range text for a
    ``CW NN``-labeled bucket."""
    start_month = week_start.strftime("%b")
    end_month = week_end.strftime("%b")
    if start_month == end_month:
        return f"{start_month} {week_start.day} - {week_end.day}"
    return f"{start_month} {week_start.day} - {end_month} {week_end.day}"


def _bucket_labels(summary: ReportSummaryResponse) -> list[tuple[str, str | None]]:
    """``(label, title)`` pairs, one per bucket, shared by :func:`_stacked_buckets` and
    :func:`_count_chart_items` so both charts use one x-axis vocabulary -- port of
    ``barsFromDays``/``barsFromWeeks`` in ``frontend/src/components/MiniBarChart/bars.ts``.

    Day buckets (``period == week``) are always <= 7 days here, so they always get the
    weekday-short label (``barsFromDays``'s longer-range ``formatShortDate`` branch never
    triggers for a single week); ``title`` is ``None`` since the label isn't an abbreviation.
    Week buckets (``month``/``quarter``) get the compact ``CW NN`` label with the full date range
    as ``title``.
    """
    if summary.period == ReportPeriod.WEEK:
        days = _zero_filled_days(summary)
        if len(days) > 7:
            return [(_format_short_date(row.date), None) for row in days]
        return [(_format_weekday_short(row.date), None) for row in days]
    return [
        (
            _calendar_week_label(row.week_start, row.week_end),
            _format_week_range_short(row.week_start, row.week_end),
        )
        for row in summary.by_week
    ]


def _category_legend(summary: ReportSummaryResponse) -> list[CategoryLegendItem]:
    """Build the stacked-chart legend from ``summary.by_category`` (already sorted by total
    minutes descending)."""
    return [
        CategoryLegendItem(
            category_id=row.category.id if row.category is not None else None,
            name=row.category.name if row.category is not None else "Uncategorized",
            color=resolve_category_color(row.category.color if row.category is not None else None),
        )
        for row in summary.by_category
    ]


def _zero_filled_days(summary: ReportSummaryResponse) -> list[ReportDayBreakdown]:
    """Zero-fill ``summary.by_day`` across ``summary.start_date..summary.end_date``.

    ``by_day`` is deliberately sparse -- see ``ReportDayBreakdown``'s docstring and
    ``app/routers/reports.py:163`` -- but the app's Reports page zero-fills it client-side before
    charting, so the exporter has to do the same to match the app's charts bucket-for-bucket.
    """
    by_date = {row.date: row for row in summary.by_day}
    days: list[ReportDayBreakdown] = []
    current = summary.start_date
    while current <= summary.end_date:
        row = by_date.get(current)
        days.append(
            row
            if row is not None
            else ReportDayBreakdown(date=current, total_minutes=0, entry_count=0, by_category=[])
        )
        current += timedelta(days=1)
    return days


def _stacked_buckets(summary: ReportSummaryResponse) -> list[StackedBucket]:
    """Build the "hours by category" chart's per-bucket data: one bucket per day (``week`` period)
    or week (``month``/``quarter`` period), each with category segments ordered to match
    :func:`_category_legend`."""
    legend = _category_legend(summary)
    order = {item.category_id: index for index, item in enumerate(legend)}
    labels = _bucket_labels(summary)

    rows: list[tuple[int, list[ReportBucketCategorySplit]]]
    if summary.period == ReportPeriod.WEEK:
        rows = [(row.total_minutes, row.by_category) for row in _zero_filled_days(summary)]
    else:
        rows = [(row.total_minutes, row.by_category) for row in summary.by_week]

    buckets = []
    for (label, title), (total, by_category) in zip(labels, rows, strict=True):
        segments = sorted(
            (
                (split.category_id, split.total_minutes)
                for split in by_category
                if split.total_minutes > 0
            ),
            key=lambda segment: order.get(segment[0], len(order)),
        )
        buckets.append(
            StackedBucket(label=label, title=title, total_minutes=total, segments=segments)
        )
    return buckets


def _count_chart_items(summary: ReportSummaryResponse) -> list[CountPoint]:
    """``CountPoint``s for the "entries per day/week" chart. Uses the same zero-filled day
    buckets (and the same :func:`_bucket_labels` labeling) as :func:`_stacked_buckets` for
    ``week`` reports, so both charts' columns/points line up 1:1."""
    labels = _bucket_labels(summary)
    if summary.period == ReportPeriod.WEEK:
        counts = [row.entry_count for row in _zero_filled_days(summary)]
    else:
        counts = [row.entry_count for row in summary.by_week]
    return [
        CountPoint(label=label, title=title, count=count)
        for (label, title), count in zip(labels, counts, strict=True)
    ]


def _safe_filename_slug(text: str) -> str:
    """Lowercase ``text`` and collapse any run of non-alphanumeric characters into a single
    ``-``, for safe use inside a downloaded filename."""
    lowered = text.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return slug or "export"


_CSV_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _csv_safe(value: object) -> object:
    """Neutralize CSV formula injection (OWASP guidance): prefix strings that start with
    ``= + - @`` or a tab/carriage-return with a single quote. Non-string values pass through."""
    if isinstance(value, str) and value.startswith(_CSV_FORMULA_PREFIXES):
        return f"'{value}"
    return value


def _get_database_label(db: sqlite3.Connection) -> str:
    """Read ``settings.database_label`` (falling back to a generic label if unset)."""
    row = db.execute("SELECT database_label FROM settings LIMIT 1").fetchone()
    label: str = row["database_label"] if row is not None else "time-tracker"
    return label


@router.get("/backup")
def export_backup(db: DbDep) -> FileResponse:
    """Download a full, consistent snapshot of the SQLite database.

    Uses SQLite's online backup API (``sqlite3.Connection.backup``) into a temporary file rather
    than reading the database file directly off disk, so the snapshot stays consistent even if a
    write is in progress on another connection concurrently. The temp file is deleted after the
    response has been sent.
    """
    label = _safe_filename_slug(_get_database_label(db))
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    filename = f"{label}-backup-{timestamp}.sqlite"

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite")
    tmp_path = tmp.name
    tmp.close()

    dest_conn = sqlite3.connect(tmp_path)
    try:
        db.backup(dest_conn)
    finally:
        dest_conn.close()

    return FileResponse(
        tmp_path,
        media_type="application/octet-stream",
        filename=filename,
        background=BackgroundTask(os.unlink, tmp_path),
    )


@router.get("/entries.csv")
def export_entries_csv(
    db: DbDep,
    start_date: date | None = None,
    end_date: date | None = None,
) -> Response:
    """Download completed entries (``end_ts IS NOT NULL``) as CSV, ``ORDER BY start_ts DESC``.

    ``start_date``/``end_date`` are optional, inclusive, and interpreted in
    ``settings.timezone`` (same bounds helper as ``GET /entries``).
    """
    if start_date is not None and end_date is not None and end_date < start_date:
        raise ValidationError(
            "end_date must be >= start_date",
            fields=[{"loc": ["query", "end_date"], "msg": "end_date must be >= start_date"}],
        )

    where_clauses: list[str] = ["entries.end_ts IS NOT NULL"]
    params: list[object] = []
    tz_name = get_settings_timezone(db) if start_date is not None or end_date is not None else None
    if start_date is not None:
        start_utc, _ = local_range_bounds_utc(tz_name or "UTC", start_date, start_date)
        where_clauses.append("entries.start_ts >= ?")
        params.append(start_utc)
    if end_date is not None:
        _, end_utc = local_range_bounds_utc(tz_name or "UTC", end_date, end_date)
        where_clauses.append("entries.start_ts <= ?")
        params.append(end_utc)

    where_sql = " AND ".join(where_clauses)
    rows = db.execute(
        f"SELECT entries.* FROM entries WHERE {where_sql} ORDER BY entries.start_ts DESC",  # noqa: S608
        params,
    ).fetchall()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id",
            "title",
            "category",
            "start_ts",
            "end_ts",
            "duration_minutes",
            "entry_mode",
            "tags",
            "notes",
        ]
    )
    for row in rows:
        category_row = (
            get_category_row(db, row["category_id"]) if row["category_id"] is not None else None
        )
        category_name = category_row["name"] if category_row is not None else ""
        tag_names = "; ".join(tag_row["name"] for tag_row in get_tags_for_entry(db, row["id"]))
        writer.writerow(
            [
                row["id"],
                _csv_safe(row["title"]),
                _csv_safe(category_name),
                row["start_ts"],
                row["end_ts"],
                row["duration_minutes"],
                row["entry_mode"],
                _csv_safe(tag_names),
                _csv_safe(row["notes"] or ""),
            ]
        )

    label = _safe_filename_slug(_get_database_label(db))
    date_stamp = datetime.now(UTC).strftime("%Y%m%d")
    filename = f"{label}-entries-{date_stamp}.csv"

    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --- HTML export -------------------------------------------------------------------------------

_HTML_STYLE = f"""
* {{ box-sizing: border-box; }}
body {{
  margin: 0; padding: 24px; background: {BG_SUBTLE}; font-family: {FONT_SANS};
  color: {TEXT}; font-size: 14px;
}}
.container {{ max-width: 900px; margin: 0 auto; display: flex; flex-direction: column; gap: 16px; }}
.card {{
  background: {SURFACE}; border: 1px solid {BORDER}; border-radius: {RADIUS_PX}px; padding: 16px;
}}
.row {{ display: flex; gap: 16px; flex-wrap: wrap; }}
.row > .card {{ flex: 1; min-width: 280px; }}
p, ul {{ margin: 0; }}
.heading {{ font-size: 20px; font-weight: bold; margin-bottom: 4px; }}
.subheading {{ font-size: 13px; color: {TEXT_SECONDARY}; }}
.section-heading {{ font-size: 16px; font-weight: bold; margin-bottom: 8px; }}
.section-heading.spaced {{ margin-top: 16px; }}
.total-value {{
  font-family: {FONT_MONO}; font-variant-numeric: tabular-nums; font-size: 28px; font-weight: bold;
}}
.mono {{ font-family: {FONT_MONO}; font-variant-numeric: tabular-nums; white-space: nowrap; }}
.legend {{
  display: flex; flex-wrap: wrap; gap: 12px; list-style: none; padding: 0; margin: 0 0 12px;
}}
.legend-item {{
  display: flex; align-items: center; gap: 4px; font-size: 12px; color: {TEXT_SECONDARY};
}}
.swatch {{ width: 10px; height: 10px; border-radius: 2px; flex-shrink: 0; display: inline-block; }}
.seg-bar {{
  display: flex; width: 100%; height: 8px; border-radius: 4px; overflow: hidden;
  margin-bottom: 8px; background: {BG_SUBTLE};
}}
.seg-legend {{ display: flex; flex-direction: column; gap: 4px; }}
.seg-legend-row {{ display: flex; align-items: center; gap: 6px; font-size: 13px; }}
.seg-legend-label {{ flex: 1; }}
.columns {{ display: flex; align-items: flex-end; height: 140px; gap: 0; }}
.column {{
  flex: 1; display: flex; flex-direction: column; align-items: center; gap: 4px; height: 100%;
}}
.col-value {{
  font-size: 12px; font-family: {FONT_MONO}; color: {TEXT_SECONDARY}; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis; max-width: 100%;
}}
.track {{ flex: 1; width: 100%; display: flex; align-items: flex-end; justify-content: center; }}
.stack {{
  width: 60%; min-height: 2px; display: flex; flex-direction: column-reverse;
  border-radius: 4px 4px 0 0; overflow: hidden;
}}
.segment {{ width: 100%; }}
.col-label {{ font-size: 12px; color: {TEXT_MUTED}; text-align: center; }}
.plot {{ position: relative; width: 100%; height: 180px; }}
.plot svg {{ position: absolute; inset: 0; width: 100%; height: 100%; display: block; }}
.plot-line {{
  fill: none; stroke: {ACCENT}; stroke-width: 2; stroke-linejoin: round; stroke-linecap: round;
}}
.point {{ position: absolute; width: 0; height: 0; }}
.marker {{
  position: absolute; left: 0; top: 0; transform: translate(-50%, -50%);
  width: 8px; height: 8px; border-radius: 50%; background: {ACCENT}; border: 1px solid {SURFACE};
}}
.count-label {{
  position: absolute; left: 0; bottom: 8px; transform: translateX(-50%); font-size: 12px;
  font-family: {FONT_MONO}; color: {TEXT_SECONDARY}; white-space: nowrap;
}}
.plot-labels {{ display: flex; }}
.plot-label {{ flex: 1; text-align: center; font-size: 12px; color: {TEXT_MUTED}; }}
.highlights {{ margin: 8px 0 0; padding-left: 20px; }}
@media (max-width: 720px) {{ .row {{ flex-direction: column; }} }}
""".strip()


def _html_segmented_bar(
    segments: list[Segment],
    empty_message: str,
    visible_limit: int | None = None,
    kind: str = "categories",
) -> str:
    """A flex-row bar (one flex-grow segment per category/tag) plus a swatch/name/time/percent
    legend, replacing the removed ``<table>``-based breakdown.

    The bar always reflects every segment; the legend list itself is capped at ``visible_limit``
    (matching ``SegmentedBreakdown.tsx``'s ``visibleLimit`` prop -- ``None`` for an uncapped
    legend, as the app uses for categories), with a "+N more <kind>" line below it for whatever's
    hidden."""
    if not segments:
        return f'<p class="subheading">{escape(empty_message)}</p>'
    bar_html = "".join(
        f'<div style="flex-grow: {max(1, round(segment.percent)) if segment.minutes else 0}; '
        f'background: {segment.color};"></div>'
        for segment in segments
        if segment.minutes
    )
    visible = segments if visible_limit is None else segments[:visible_limit]
    hidden_count = 0 if visible_limit is None else max(0, len(segments) - visible_limit)
    legend_rows = "".join(
        '<div class="seg-legend-row">'
        f'<span class="swatch" style="background: {segment.color};"></span>'
        f'<span class="seg-legend-label">{escape(segment.label)}</span>'
        f'<span class="mono">{escape(format_minutes(segment.minutes))}</span>'
        f"<span>{round(segment.percent)}%</span>"
        "</div>"
        for segment in visible
    )
    more_html = (
        f'<p class="subheading" style="margin-top: 4px;">+ {hidden_count} more {escape(kind)}</p>'
        if hidden_count
        else ""
    )
    return (
        f'<div class="seg-bar">{bar_html}</div><div class="seg-legend">{legend_rows}</div>'
        f"{more_html}"
    )


def _html_stacked_chart(
    buckets: list[StackedBucket], legend: list[CategoryLegendItem], empty_message: str
) -> str:
    """Port of ``StackedCategoryChart.tsx``: a legend, then one flex column per bucket, each a
    vertical stack of category-colored blocks sized by ``flex-grow`` (so a block's height is
    exactly its share of the bucket), the whole stack's height set via an inline ``height: N%``
    against the period's busiest bucket."""
    if not buckets or not legend:
        return f'<p class="subheading">{escape(empty_message)}</p>'
    color_by_id = {item.category_id: item.color for item in legend}
    name_by_id = {item.category_id: item.name for item in legend}
    max_total = max((bucket.total_minutes for bucket in buckets), default=0) or 1

    legend_html = "".join(
        f'<li class="legend-item"><span class="swatch" style="background: {item.color};">'
        f"</span>{escape(item.name)}</li>"
        for item in legend
    )

    columns_html = []
    for bucket in buckets:
        stack_height = round(100 * bucket.total_minutes / max_total) if bucket.total_minutes else 0
        segments_html = "".join(
            f'<div class="segment" style="flex-grow: {minutes}; '
            f'background: {color_by_id.get(cat_id, FALLBACK_CAT)};" '
            f'title="{escape(name_by_id.get(cat_id, "Uncategorized"))}: '
            f'{escape(format_minutes(minutes))}"></div>'
            for cat_id, minutes in bucket.segments
        )
        columns_html.append(
            '<div class="column" title="'
            f"{escape(bucket.title or bucket.label)}: "
            f'{escape(format_minutes(bucket.total_minutes))}">'
            f'<span class="col-value">{escape(format_minutes(bucket.total_minutes))}</span>'
            f'<div class="track"><div class="stack" style="height: {stack_height}%;">'
            f"{segments_html}</div></div>"
            f'<span class="col-label">{escape(bucket.label)}</span></div>'
        )
    return (
        f'<ul class="legend">{legend_html}</ul><div class="columns">{"".join(columns_html)}</div>'
    )


def _html_count_chart(points: list[CountPoint], empty_message: str) -> str:
    """Port of ``CountLineChart.tsx``: an SVG polyline (``preserveAspectRatio="none"``,
    ``vector-effect="non-scaling-stroke"``) plus HTML marker/label elements layered over it at the
    same ``(x%, y%)`` coordinates -- markers stay circular even though the SVG itself is
    non-uniformly scaled to fill a wide, short box (see ``CountLineChart.tsx``'s docstring for
    why SVG ``<circle>``s can't be used directly)."""
    if not points:
        return f'<p class="subheading">{escape(empty_message)}</p>'
    count = len(points)
    max_value = max(point.count for point in points) or 1
    top_headroom = 22.0
    bottom_margin = 6.0
    usable = 100.0 - top_headroom - bottom_margin

    coords = []
    for index, point in enumerate(points):
        x = (index + 0.5) / count * 100
        y = top_headroom + usable * (1 - point.count / max_value)
        coords.append((point, x, y))

    polyline = ""
    if len(coords) > 1:
        points_attr = " ".join(f"{x:.2f},{y:.2f}" for _, x, y in coords)
        polyline = (
            f'<polyline class="plot-line" vector-effect="non-scaling-stroke" '
            f'points="{points_attr}"></polyline>'
        )

    markers = "".join(
        f'<div class="point" style="left: {x:.2f}%; top: {y:.2f}%;">'
        f'<span class="count-label">{point.count}</span>'
        f'<span class="marker" title="{escape(point.title or point.label)}: {point.count} '
        f'{"entry" if point.count == 1 else "entries"}"></span></div>'
        for point, x, y in coords
    )
    labels_html = "".join(
        f'<span class="plot-label">{escape(point.label)}</span>' for point, _, _ in coords
    )

    return (
        '<div class="plot" role="img" aria-label="Number of entries per bucket">'
        f'<svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">{polyline}</svg>'
        f"{markers}</div>"
        f'<div class="plot-labels">{labels_html}</div>'
    )


def _render_report_html(summary: ReportSummaryResponse) -> str:
    """Render ``summary`` as a self-contained HTML document mirroring the Reports page
    (``ReportsPage.tsx``): a two-column top row (date range/total, category/tag breakdowns), a
    "Hours by category" stacked chart, an "Entries per day/week" line chart, then the narrative
    summary. Fully self-contained (a single inline ``<style>`` block, an inline ``<svg>`` for the
    line chart, no external CSS/fonts/images/JS) -- there is no Outlook-compatibility constraint
    on this export.
    """
    period_label = summary.period.value.capitalize()
    entry_word = "entry" if summary.entry_count == 1 else "entries"

    category_segments, tag_segments = _segment_items(summary)
    legend = _category_legend(summary)
    stacked_buckets = _stacked_buckets(summary)
    count_items = _count_chart_items(summary)
    narrative, highlights = build_narrative(summary)
    count_title = "Entries per " + ("day" if summary.period == ReportPeriod.WEEK else "week")

    top_row = (
        '<div class="row">'
        '<div class="card">'
        f'<p class="heading">Time Tracker Report &mdash; {escape(period_label)}</p>'
        f'<p class="subheading">{summary.start_date.isoformat()} to '
        f"{summary.end_date.isoformat()} ({escape(summary.timezone)})</p>"
        '<p class="section-heading spaced">Total time</p>'
        f'<p class="total-value">{format_minutes(summary.total_minutes)}</p>'
        f'<p class="subheading">{summary.entry_count} {entry_word}</p>'
        "</div>"
        '<div class="card">'
        '<p class="section-heading">By category</p>'
        + _html_segmented_bar(category_segments, "No entries.")
        + '<p class="section-heading spaced">By tag</p>'
        + _html_segmented_bar(
            tag_segments, "No tagged entries.", visible_limit=_TAG_VISIBLE_LIMIT, kind="tags"
        )
        + "</div>"
        "</div>"
    )

    stacked_card = (
        '<div class="card"><p class="section-heading">Hours by category</p>'
        + _html_stacked_chart(stacked_buckets, legend, "No entries.")
        + "</div>"
    )

    count_card = (
        f'<div class="card"><p class="section-heading">{escape(count_title)}</p>'
        + _html_count_chart(count_items, "No entries.")
        + "</div>"
    )

    highlights_html = "".join(f"<li>{escape(item)}</li>" for item in highlights)
    summary_card = (
        '<div class="card"><p class="section-heading">Summary</p>'
        f"<p>{escape(narrative)}</p>"
        f'<ul class="highlights">{highlights_html}</ul></div>'
    )

    body = f'<div class="container">{top_row}{stacked_card}{count_card}{summary_card}</div>'

    return (
        "<!DOCTYPE html>"
        f'<html><head><meta charset="utf-8"><style>{_HTML_STYLE}</style></head>'
        f"<body>{body}</body></html>"
    )


@router.get("/report.html")
def export_report_html(
    db: DbDep,
    period: ReportPeriod,
    date: date | None = None,
) -> Response:
    """View an HTML report for the week/month/quarter containing ``date``.

    Reuses ``GET /reports/summary``'s aggregation (``get_reports_summary``) and renders it as a
    single self-contained HTML document. Returned inline (``Content-Disposition`` is not set to
    ``attachment``) so it renders directly in a browser.
    """
    summary = get_reports_summary(db, period, date)
    html = _render_report_html(summary)
    return Response(content=html, media_type="text/html")


# --- Markdown export --------------------------------------------------------------------------

_MD_BAR_WIDTH = 20
"""Max number of ``█`` characters for the fullest bar in a Markdown chart."""


def _md_escape(text: str) -> str:
    """Escape ``|`` (Markdown table cell delimiter) in user-derived text, so a category/tag named
    e.g. ``a|b`` doesn't corrupt the surrounding table."""
    return text.replace("|", "\\|")


def _md_bucket_label(label: str, title: str | None) -> str:
    """Markdown has no tooltip, so an abbreviated bucket ``label`` (``CW 27``) carries its full
    date range inline instead, mirroring the HTML export's ``title`` attribute."""
    return f"{label} ({title})" if title else label


def _md_escape_prose(text: str) -> str:
    """Escape free-form narrative/highlight prose for Markdown embedding.

    ``build_narrative`` interpolates raw category/tag names into ``narrative``/``highlights``,
    and those names have no character restrictions -- an embedded newline could otherwise start a
    new Markdown block (e.g. inject a fake ``#`` heading) inside the Summary section, so any
    run of whitespace containing a newline is collapsed to a single space. ``|`` is also escaped
    for consistency with :func:`_md_escape`, even though prose (unlike a table cell) doesn't
    strictly require it.
    """
    collapsed = re.sub(r"[ \t]*\r?\n[ \t]*", " ", text)
    return _md_escape(collapsed)


def _md_bar_chart(items: list[tuple[str, int]], empty_message: str) -> str:
    """Render ``items`` as a Markdown table with ``█`` block-character bars proportional to the
    largest value."""
    if not items:
        return f"_{empty_message}_\n"
    max_value = max(value for _, value in items)
    lines = ["| | | Value |", "|---|---|---|"]
    for label, value in items:
        filled = round(_MD_BAR_WIDTH * value / max_value) if max_value else 0
        bar = "█" * filled + "░" * (_MD_BAR_WIDTH - filled)
        lines.append(f"| {_md_escape(label)} | `{bar}` | {value} |")
    return "\n".join(lines) + "\n"


def _md_segment_table(
    label_header: str,
    segments: list[Segment],
    empty_message: str,
    visible_limit: int | None = None,
    kind: str = "categories",
) -> str:
    """Render a category/tag segmented breakdown as a Markdown table: ``| <label_header> | Color |
    Time | % | Bar |``, with a proportional ``█``/``░`` bar and the literal hex color text.

    The table itself is capped at ``visible_limit`` rows (``None`` for uncapped, as the app uses
    for categories -- see ``SegmentedBreakdown.tsx``'s ``visibleLimit`` prop), with a "+N more
    <kind>" line appended for whatever's hidden."""
    if not segments:
        return f"_{empty_message}_\n"
    max_percent = max(segment.percent for segment in segments)
    visible = segments if visible_limit is None else segments[:visible_limit]
    hidden_count = 0 if visible_limit is None else max(0, len(segments) - visible_limit)
    lines = [f"| {label_header} | Color | Time | % | Bar |", "|---|---|---|---|---|"]
    for segment in visible:
        filled = round(_MD_BAR_WIDTH * segment.percent / max_percent) if max_percent else 0
        bar = "█" * filled + "░" * (_MD_BAR_WIDTH - filled)
        lines.append(
            f"| {_md_escape(segment.label)} | {segment.color} | "
            f"{format_minutes(segment.minutes)} | {round(segment.percent)}% | `{bar}` |"
        )
    result = "\n".join(lines) + "\n"
    if hidden_count:
        result += f"\n_+ {hidden_count} more {kind}_\n"
    return result


def _render_report_markdown(summary: ReportSummaryResponse) -> str:
    """Render ``summary`` as Markdown: content parity with :func:`_render_report_html` (header,
    total, category/tag breakdowns, hours-by-category chart, entry-count chart, narrative summary)
    -- no visual restyling, no embedded raw HTML, and no data tables beyond the segmented
    breakdown/bar-chart tables that already encode a chart."""
    period_label = summary.period.value.capitalize()
    entry_word = "entry" if summary.entry_count == 1 else "entries"

    category_segments, tag_segments = _segment_items(summary)
    stacked_buckets = _stacked_buckets(summary)
    count_items = _count_chart_items(summary)
    narrative, highlights = build_narrative(summary)

    sections = [
        f"# Time Tracker Report — {period_label}",
        "",
        f"{summary.start_date.isoformat()} to {summary.end_date.isoformat()} ({summary.timezone})",
        "",
        "## Total time",
        "",
        f"**{format_minutes(summary.total_minutes)}** across {summary.entry_count} {entry_word}",
        "",
        "## By category",
        "",
        _md_segment_table("Category", category_segments, "No entries."),
        "## By tag",
        "",
        _md_segment_table(
            "Tag",
            tag_segments,
            "No tagged entries.",
            visible_limit=_TAG_VISIBLE_LIMIT,
            kind="tags",
        ),
        "## Hours by category",
        "",
        _md_bar_chart(
            [
                (_md_bucket_label(bucket.label, bucket.title), bucket.total_minutes)
                for bucket in stacked_buckets
            ],
            "No entries.",
        ),
        f"## Entries per {'day' if summary.period == ReportPeriod.WEEK else 'week'}",
        "",
        _md_bar_chart(
            [(_md_bucket_label(point.label, point.title), point.count) for point in count_items],
            "No entries.",
        ),
        "## Summary",
        "",
        _md_escape_prose(narrative),
        "",
        *[f"- {_md_escape_prose(highlight)}" for highlight in highlights],
    ]
    return "\n".join(sections) + "\n"


@router.get("/report.md")
def export_report_markdown(
    db: DbDep,
    period: ReportPeriod,
    date: date | None = None,
) -> Response:
    """Download a Markdown report for the week/month/quarter containing ``date``.

    Reuses ``GET /reports/summary``'s aggregation (``get_reports_summary``) — same content as
    ``GET /exports/report.html``, rendered as Markdown tables with ``█`` block-character bar
    charts instead of HTML.
    """
    summary = get_reports_summary(db, period, date)
    markdown = _render_report_markdown(summary)
    filename = _report_filename(db, "md")
    return Response(
        content=markdown,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --- PDF export --------------------------------------------------------------------------------

_PDF_PAGE_WIDTH_MM = 210.0
_PDF_MARGIN_MM = 15.0
_PDF_CONTENT_WIDTH_MM = _PDF_PAGE_WIDTH_MM - 2 * _PDF_MARGIN_MM

_PDF_CARD_PADDING_MM = 4.0
_PDF_ROW_GUTTER_MM = 6.0

_PDF_BORDER_RGB = hex_to_rgb(BORDER)
_PDF_TEXT_RGB = hex_to_rgb(TEXT)
_PDF_TEXT_SECONDARY_RGB = hex_to_rgb(TEXT_SECONDARY)
_PDF_WHITE_RGB = (255, 255, 255)
_PDF_ACCENT_RGB = hex_to_rgb(ACCENT)
_PDF_FALLBACK_RGB = hex_to_rgb(FALLBACK_CAT)


def _pdf_safe(text: str) -> str:
    """Make ``text`` safe to pass to ``fpdf2``'s core (non-embedded) Helvetica font.

    fpdf2's built-in fonts only support Latin-1 (they're not embedded Unicode TTFs), so any
    character outside Latin-1 — e.g. emoji or CJK text, both plausible in a user-entered category
    or tag name — raises ``FPDFUnicodeEncodingException`` and turns a report download into a 500.
    Rather than shipping a ~700KB Unicode TTF for an offline personal app, this deliberately and
    lossily degrades unsupported characters to ``?`` (``str.encode(..., errors="replace")``), same
    as Python's own ``latin-1`` codec error handling. HTML and Markdown exports are unaffected and
    render the original characters intact.
    """
    return text.encode("latin-1", "replace").decode("latin-1")


def _pdf_truncate_label(label: str, max_chars: int) -> str:
    """Truncate ``label`` to ``max_chars`` with a trailing ``...`` so a cut label is visibly
    incomplete rather than silently chopped. Uses ASCII dots (not ``…``) since this feeds into the
    Latin-1-only core PDF font."""
    if len(label) <= max_chars:
        return label
    return label[: max_chars - 3] + "..."


def _pdf_reset_colors(pdf: FPDF) -> None:
    """Reset draw/fill/text color state -- ``fpdf2``'s color state is sticky across cells/rects,
    so each section must reset it or it leaks colors from the previous section."""
    pdf.set_draw_color(0, 0, 0)
    pdf.set_fill_color(*_PDF_WHITE_RGB)
    pdf.set_text_color(*_PDF_TEXT_RGB)


def _pdf_section_heading(pdf: FPDF, text: str) -> None:
    pdf.set_font("Helvetica", "B", 13)
    pdf.ln(4)
    pdf.cell(0, 8, _pdf_safe(text), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)


def _pdf_draw_card_border(pdf: FPDF, x: float, y: float, width: float, height: float) -> None:
    """Draw a ``BORDER``-stroked, rounded-corner card rectangle, falling back to a square-cornered
    rect on older ``fpdf2`` without ``round_corners`` support."""
    pdf.set_draw_color(*_PDF_BORDER_RGB)
    try:
        pdf.rect(x, y, width, height, style="D", round_corners=True, corner_radius=2.0)
    except TypeError:
        pdf.rect(x, y, width, height, style="D")


@contextmanager
def _pdf_card(pdf: FPDF) -> Iterator[None]:
    """Draw a ``BORDER``-stroked "card" rectangle around a block of content.

    The border is drawn *after* the content (using the recorded start/end Y), since the content's
    height is variable (narrative text, highlights) and isn't known up front. Drawing the rect
    after the content -- rather than filling it first -- also avoids a filled rect covering
    already-rendered text (later draws paint over earlier ones in PDF page order); this is fine
    since the page background is already ``SURFACE`` (white), so a fill would be visually
    redundant anyway.

    If the content spans a page break (``fpdf``'s automatic pagination), ``y_end`` is measured on
    a later page than ``y_start`` and is no longer comparable to it -- computing ``y_end -
    y_start`` would yield a bogus (often negative) height and draw a stray full-page border box.
    Rather than reaching into ``fpdf``'s internal per-page content buffers to draw a border
    segment on each spanned page (fragile, and not worth it for a cosmetic border), the border is
    simply skipped for cards that span a page break; the content itself still renders normally.
    """
    x_start = pdf.get_x()
    y_start = pdf.get_y()
    page_start = pdf.page_no()
    pdf.set_xy(x_start, y_start + _PDF_CARD_PADDING_MM)
    try:
        yield
    finally:
        y_end = pdf.get_y()
        page_end = pdf.page_no()
        if page_end == page_start:
            height = y_end - y_start + _PDF_CARD_PADDING_MM
            _pdf_draw_card_border(pdf, x_start, y_start, _PDF_CONTENT_WIDTH_MM, height)
        pdf.set_xy(x_start, y_end + _PDF_CARD_PADDING_MM + 6)
        _pdf_reset_colors(pdf)


def _pdf_two_column_row(
    pdf: FPDF,
    left: Callable[[FPDF, float, float, float], float],
    right: Callable[[FPDF, float, float, float], float],
    left_height: float,
    right_height: float,
) -> None:
    """Render two cards side by side: ``left``/``right`` each draw their content at the given
    ``(x, y, width)`` and return the y they finished at; both card borders are then drawn at
    ``height = max(left_end_y, right_end_y)``, so a shorter card's border still reaches the taller
    one's bottom edge. Auto page break is disabled for the row's duration (a break partway through
    one column would desynchronize the two columns' y-coordinates) and restored afterwards.

    ``left_height``/``right_height`` are the caller's *pre-computed* (not drawn) estimates of each
    column's content height -- since auto page break is off for the row, ``fpdf2`` cannot
    paginate mid-row: any content drawn past the physical page bottom is silently dropped (no
    exception, no artifact). If ``max(left_height, right_height)`` wouldn't fit in the space
    remaining on the page, this falls back to rendering both cards full-width and stacked (the
    normal :func:`_pdf_card` path, which paginates normally) instead of risking silent truncation.
    """
    half_width = (_PDF_CONTENT_WIDTH_MM - _PDF_ROW_GUTTER_MM) / 2
    x_start = pdf.get_x()
    y_start = pdf.get_y()

    estimated_height = max(left_height, right_height) + 2 * _PDF_CARD_PADDING_MM
    available_height = pdf.h - _PDF_MARGIN_MM - y_start
    if estimated_height > available_height:
        with _pdf_card(pdf):
            left(pdf, pdf.get_x(), pdf.get_y(), _PDF_CONTENT_WIDTH_MM)
        with _pdf_card(pdf):
            right(pdf, pdf.get_x(), pdf.get_y(), _PDF_CONTENT_WIDTH_MM)
        return

    saved_auto, saved_margin = pdf.auto_page_break, pdf.b_margin
    pdf.set_auto_page_break(auto=False)
    try:
        content_width = half_width - 2 * _PDF_CARD_PADDING_MM
        left_end_y = left(
            pdf, x_start + _PDF_CARD_PADDING_MM, y_start + _PDF_CARD_PADDING_MM, content_width
        )
        right_x = x_start + half_width + _PDF_ROW_GUTTER_MM
        right_end_y = right(
            pdf, right_x + _PDF_CARD_PADDING_MM, y_start + _PDF_CARD_PADDING_MM, content_width
        )
    finally:
        pdf.set_auto_page_break(auto=saved_auto, margin=saved_margin)

    height = max(left_end_y, right_end_y) - y_start + _PDF_CARD_PADDING_MM
    _pdf_draw_card_border(pdf, x_start, y_start, half_width, height)
    _pdf_draw_card_border(
        pdf, x_start + half_width + _PDF_ROW_GUTTER_MM, y_start, half_width, height
    )
    pdf.set_xy(x_start, y_start + height + 6)
    _pdf_reset_colors(pdf)


def _pdf_summary_card(
    pdf: FPDF,
    x: float,
    y: float,
    width: float,
    summary: ReportSummaryResponse,
    period_label: str,
    entry_word: str,
) -> float:
    """Left card of the PDF's top row: title, date range, total time, entry count."""
    pdf.set_xy(x, y)
    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(width, 7, _pdf_safe(f"Time Tracker Report - {period_label}"), align="L")
    pdf.set_x(x)
    pdf.set_text_color(*_PDF_TEXT_SECONDARY_RGB)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(
        width,
        5,
        _pdf_safe(
            f"{summary.start_date.isoformat()} to {summary.end_date.isoformat()} "
            f"({summary.timezone})"
        ),
        align="L",
    )
    pdf.set_text_color(*_PDF_TEXT_RGB)
    pdf.set_x(x)
    pdf.ln(4)
    pdf.set_x(x)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(width, 6, "Total time", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(x)
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(
        width, 9, _pdf_safe(format_minutes(summary.total_minutes)), new_x="LMARGIN", new_y="NEXT"
    )
    pdf.set_x(x)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*_PDF_TEXT_SECONDARY_RGB)
    pdf.cell(
        width, 6, _pdf_safe(f"{summary.entry_count} {entry_word}"), new_x="LMARGIN", new_y="NEXT"
    )
    pdf.set_text_color(*_PDF_TEXT_RGB)
    return pdf.get_y()


def _pdf_measure_line_count(
    pdf: FPDF, width: float, text: str, font_size: float, font_style: str = ""
) -> int:
    """Count how many lines ``text`` wraps to at ``(font_style, font_size)`` within ``width``,
    without drawing anything (``multi_cell(..., dry_run=True, output="LINES")``) -- used to
    estimate content height up front for :func:`_pdf_two_column_row`, which needs to know a
    card's height *before* committing to draw it (auto page break is off for that row, so an
    under-estimate risks silently dropping content past the page bottom)."""
    saved_family, saved_style, saved_size = pdf.font_family, pdf.font_style, pdf.font_size_pt
    pdf.set_font("Helvetica", font_style, font_size)
    lines = pdf.multi_cell(width, font_size, _pdf_safe(text), dry_run=True, output="LINES")
    pdf.set_font(saved_family, saved_style, saved_size)
    return len(lines) if isinstance(lines, list) else 1


def _pdf_summary_card_height(
    pdf: FPDF,
    summary: ReportSummaryResponse,
    period_label: str,
    width: float,
) -> float:
    """Mirror of :func:`_pdf_summary_card`'s vertical extent, computed without drawing anything --
    see :func:`_pdf_two_column_row`."""
    title_lines = _pdf_measure_line_count(
        pdf, width, f"Time Tracker Report - {period_label}", 16, "B"
    )
    subtitle = (
        f"{summary.start_date.isoformat()} to {summary.end_date.isoformat()} ({summary.timezone})"
    )
    subtitle_lines = _pdf_measure_line_count(pdf, width, subtitle, 10)
    return title_lines * 7.0 + subtitle_lines * 5.0 + 4.0 + 6.0 + 9.0 + 6.0


def _pdf_segment_bar_widths(segments: list[Segment], width: float) -> list[float]:
    """Compute each segment's bar width within ``width``: proportional to ``percent``, floored at
    1mm so a tiny (< ~1.2% at typical card widths) segment stays visible, then scaled back down
    proportionally if that floor pushed the total past ``width`` -- percentages already sum to
    100, so the *unfloored* widths already sum to exactly ``width``, and the floor only ever adds
    width, never reclaims it. Without the rescale, one small-share segment is enough to push the
    bar past its card's right edge and over the border."""
    raw = [width * segment.percent / 100 if segment.minutes else 0.0 for segment in segments]
    floored = [0.0 if value == 0.0 else max(1.0, value) for value in raw]
    total = sum(floored)
    if total > width and total > 0:
        scale = width / total
        floored = [value * scale for value in floored]
    return floored


def _pdf_segmented_bar(
    pdf: FPDF,
    segments: list[Segment],
    empty_message: str,
    width: float,
    visible_limit: int | None = None,
    kind: str = "categories",
) -> None:
    """Draw a category/tag segmented breakdown within ``width``: adjacent filled rects sized by
    ``percent`` (see :func:`_pdf_segment_bar_widths` for how they're kept within ``width``),
    followed by a legend row (swatch, label, duration, rounded percent) per segment.

    The bar always reflects every segment; the legend list is capped at ``visible_limit``
    (``None`` for uncapped, as the app uses for categories -- see ``SegmentedBreakdown.tsx``'s
    ``visibleLimit`` prop), with a "+N more <kind>" line for whatever's hidden.
    """
    if not segments:
        pdf.cell(width, 6, _pdf_safe(empty_message), new_x="LMARGIN", new_y="NEXT")
        return

    bar_height = 6.0
    x_start = pdf.get_x()
    y_start = pdf.get_y()
    cursor_x = x_start
    for segment, seg_width in zip(segments, _pdf_segment_bar_widths(segments, width), strict=True):
        if seg_width <= 0:
            continue
        pdf.set_fill_color(*hex_to_rgb(segment.color))
        pdf.rect(cursor_x, y_start, seg_width, bar_height, style="F")
        cursor_x += seg_width
    pdf.set_fill_color(*_PDF_WHITE_RGB)
    pdf.set_xy(x_start, y_start + bar_height + 2)

    visible = segments if visible_limit is None else segments[:visible_limit]
    hidden_count = 0 if visible_limit is None else max(0, len(segments) - visible_limit)

    label_width = width * 0.55
    time_width = width * 0.27
    percent_width = width - label_width - time_width
    pdf.set_font("Helvetica", "", 9)
    for segment in visible:
        swatch_x = pdf.get_x()
        swatch_y = pdf.get_y()
        pdf.set_fill_color(*hex_to_rgb(segment.color))
        pdf.rect(swatch_x, swatch_y + 1, 3, 3, style="F")
        pdf.set_fill_color(*_PDF_WHITE_RGB)
        pdf.set_x(swatch_x + 5)
        pdf.cell(label_width - 5, 5, _pdf_safe(_pdf_truncate_label(segment.label, 26)))
        pdf.cell(time_width, 5, _pdf_safe(format_minutes(segment.minutes)))
        pdf.cell(percent_width, 5, f"{round(segment.percent)}%", new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(x_start)
    if hidden_count:
        pdf.set_text_color(*_PDF_TEXT_SECONDARY_RGB)
        pdf.cell(
            width, 5, _pdf_safe(f"+ {hidden_count} more {kind}"), new_x="LMARGIN", new_y="NEXT"
        )
        pdf.set_text_color(*_PDF_TEXT_RGB)
        pdf.set_x(x_start)
    pdf.set_font("Helvetica", "", 10)


def _pdf_segmented_bar_height(segments: list[Segment], visible_limit: int | None = None) -> float:
    """Mirror of :func:`_pdf_segmented_bar`'s vertical extent, computed without drawing anything
    -- used to estimate the two-column top row's required height up front (see
    :func:`_pdf_two_column_row`)."""
    if not segments:
        return 6.0
    visible_count = len(segments) if visible_limit is None else min(len(segments), visible_limit)
    hidden_count = 0 if visible_limit is None else max(0, len(segments) - visible_limit)
    height = 6.0 + 2.0 + visible_count * 5.0
    if hidden_count:
        height += 5.0
    return height


def _pdf_breakdown_card(
    pdf: FPDF,
    x: float,
    y: float,
    width: float,
    category_segments: list[Segment],
    tag_segments: list[Segment],
) -> float:
    """Right card of the PDF's top row: the "By category" and "By tag" segmented breakdowns.
    Categories are shown in full; the tag legend is capped at :data:`_TAG_VISIBLE_LIMIT`, matching
    the app."""
    pdf.set_xy(x, y)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(width, 7, "By category", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(x)
    pdf.set_font("Helvetica", "", 9)
    _pdf_segmented_bar(pdf, category_segments, "No entries.", width)
    pdf.set_x(x)
    pdf.ln(4)
    pdf.set_x(x)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(width, 7, "By tag", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(x)
    pdf.set_font("Helvetica", "", 9)
    _pdf_segmented_bar(
        pdf,
        tag_segments,
        "No tagged entries.",
        width,
        visible_limit=_TAG_VISIBLE_LIMIT,
        kind="tags",
    )
    pdf.set_font("Helvetica", "", 10)
    return pdf.get_y()


def _pdf_breakdown_card_height(
    category_segments: list[Segment], tag_segments: list[Segment]
) -> float:
    """Mirror of :func:`_pdf_breakdown_card`'s vertical extent, computed without drawing anything
    -- see :func:`_pdf_two_column_row`."""
    category_height = _pdf_segmented_bar_height(category_segments)
    tag_height = _pdf_segmented_bar_height(tag_segments, visible_limit=_TAG_VISIBLE_LIMIT)
    return 7.0 + category_height + 4.0 + 7.0 + tag_height


def _pdf_stacked_chart(
    pdf: FPDF,
    buckets: list[StackedBucket],
    legend: list[CategoryLegendItem],
    empty_message: str,
) -> None:
    """Draw the "Hours by category" chart: a swatch/name legend, then one vertical stacked column
    per bucket (filled rects, height proportional to the busiest bucket, each segment
    proportional to its share of its bucket) with a mono total above and a label below."""
    if not buckets or not legend:
        pdf.cell(0, 6, _pdf_safe(empty_message), new_x="LMARGIN", new_y="NEXT")
        return

    color_by_id = {item.category_id: hex_to_rgb(item.color) for item in legend}

    pdf.set_font("Helvetica", "", 8)
    legend_x = pdf.get_x()
    right_edge = _PDF_MARGIN_MM + _PDF_CONTENT_WIDTH_MM
    for item in legend:
        swatch_x = pdf.get_x()
        swatch_y = pdf.get_y()
        pdf.set_fill_color(*hex_to_rgb(item.color))
        pdf.rect(swatch_x, swatch_y + 1, 3, 3, style="F")
        pdf.set_fill_color(*_PDF_WHITE_RGB)
        pdf.set_x(swatch_x + 5)
        label = _pdf_safe(_pdf_truncate_label(item.name, 20))
        label_width = pdf.get_string_width(label) + 8
        if pdf.get_x() + label_width > right_edge:
            pdf.ln(6)
            pdf.set_x(legend_x)
        pdf.cell(label_width, 5, label)
    pdf.ln(9)
    pdf.set_x(legend_x)
    pdf.set_font("Helvetica", "", 10)

    chart_height = 40.0
    gap = 1.5
    bucket_count = len(buckets)
    col_width = max(1.0, _PDF_CONTENT_WIDTH_MM / bucket_count - gap)
    max_total = max((bucket.total_minutes for bucket in buckets), default=0) or 1

    x_start = pdf.get_x()
    y_top = pdf.get_y()

    pdf.set_font("Helvetica", "", 6)
    for index, bucket in enumerate(buckets):
        cx = x_start + index * (col_width + gap)
        pdf.set_xy(cx, y_top)
        pdf.cell(col_width, 4, _pdf_safe(format_minutes(bucket.total_minutes)), align="C")

    baseline_y = y_top + 4 + chart_height
    for index, bucket in enumerate(buckets):
        cx = x_start + index * (col_width + gap)
        stack_height = (
            (chart_height * bucket.total_minutes / max_total) if bucket.total_minutes else 0.0
        )
        seg_y = baseline_y
        for cat_id, minutes in bucket.segments:
            seg_height = (
                stack_height * minutes / bucket.total_minutes if bucket.total_minutes else 0.0
            )
            if seg_height <= 0:
                continue
            seg_y -= seg_height
            pdf.set_fill_color(*color_by_id.get(cat_id, _PDF_FALLBACK_RGB))
            pdf.rect(cx, seg_y, col_width, seg_height, style="F")
    pdf.set_fill_color(*_PDF_WHITE_RGB)

    for index, bucket in enumerate(buckets):
        cx = x_start + index * (col_width + gap)
        pdf.set_xy(cx, baseline_y + 2)
        pdf.cell(col_width, 4, _pdf_safe(_pdf_truncate_label(bucket.label, 10)), align="C")

    pdf.set_font("Helvetica", "", 10)
    pdf.set_xy(x_start, baseline_y + 8)


def _pdf_count_line_chart(pdf: FPDF, points: list[CountPoint], empty_message: str) -> None:
    """Draw the "Entries per day/week" chart: a polyline through filled-circle markers (real
    vector drawing, not an image), one count label above each marker, bucket labels along the
    bottom -- using the same ``(i + 0.5) / N`` x-slots as :func:`_pdf_stacked_chart`, so points
    line up with that chart's columns. The PDF has no tooltips, so ``point.title`` (the full date
    range behind an abbreviated ``CW NN`` label) isn't used here -- only in HTML/Markdown."""
    if not points:
        pdf.cell(0, 6, _pdf_safe(empty_message), new_x="LMARGIN", new_y="NEXT")
        return

    count = len(points)
    max_value = max(point.count for point in points) or 1
    plot_height = 40.0
    top_headroom = 6.0
    usable = plot_height - top_headroom

    x_start = pdf.get_x()
    y_top = pdf.get_y() + top_headroom

    coords = []
    for index, point in enumerate(points):
        x = x_start + (index + 0.5) / count * _PDF_CONTENT_WIDTH_MM
        y = y_top + usable * (1 - point.count / max_value)
        coords.append((point, x, y))

    if len(coords) > 1:
        pdf.set_draw_color(*_PDF_ACCENT_RGB)
        pdf.set_line_width(0.5)
        pdf.polyline([(x, y) for _, x, y in coords])
        pdf.set_line_width(0.2)

    pdf.set_font("Helvetica", "", 7)
    slot_width = _PDF_CONTENT_WIDTH_MM / count
    for point, x, y in coords:
        pdf.set_fill_color(*_PDF_ACCENT_RGB)
        pdf.circle(x, y, 1.3, style="F")
        pdf.set_xy(x - slot_width / 2, y - top_headroom)
        pdf.cell(slot_width, 4, _pdf_safe(str(point.count)), align="C")
    pdf.set_fill_color(*_PDF_WHITE_RGB)

    baseline_y = y_top + usable
    for index, point in enumerate(points):
        cx = x_start + index * slot_width
        pdf.set_xy(cx, baseline_y + 4)
        pdf.cell(slot_width, 4, _pdf_safe(_pdf_truncate_label(point.label, 10)), align="C")

    pdf.set_font("Helvetica", "", 10)
    pdf.set_draw_color(0, 0, 0)
    pdf.set_xy(x_start, baseline_y + 10)


def _render_report_pdf(summary: ReportSummaryResponse) -> bytes:
    """Render ``summary`` as a PDF mirroring the Reports page (a two-column top row of date
    range/total and category/tag breakdowns, a "Hours by category" stacked chart, an "Entries per
    day/week" line chart, then the narrative summary), drawn with ``fpdf2`` (pure Python, no
    system libraries -- unlike e.g. weasyprint, which needs cairo/pango and is unsuitable for an
    offline local app)."""
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=_PDF_MARGIN_MM)
    pdf.set_margins(_PDF_MARGIN_MM, _PDF_MARGIN_MM, _PDF_MARGIN_MM)
    pdf.add_page()
    _pdf_reset_colors(pdf)

    period_label = summary.period.value.capitalize()
    entry_word = "entry" if summary.entry_count == 1 else "entries"
    category_segments, tag_segments = _segment_items(summary)
    legend = _category_legend(summary)
    stacked_buckets = _stacked_buckets(summary)
    count_items = _count_chart_items(summary)

    def render_left(pdf: FPDF, x: float, y: float, width: float) -> float:
        return _pdf_summary_card(pdf, x, y, width, summary, period_label, entry_word)

    def render_right(pdf: FPDF, x: float, y: float, width: float) -> float:
        return _pdf_breakdown_card(pdf, x, y, width, category_segments, tag_segments)

    row_content_width = (_PDF_CONTENT_WIDTH_MM - _PDF_ROW_GUTTER_MM) / 2 - 2 * _PDF_CARD_PADDING_MM
    left_height = _pdf_summary_card_height(pdf, summary, period_label, row_content_width)
    right_height = _pdf_breakdown_card_height(category_segments, tag_segments)
    _pdf_two_column_row(pdf, render_left, render_right, left_height, right_height)

    with _pdf_card(pdf):
        _pdf_section_heading(pdf, "Hours by category")
        _pdf_stacked_chart(pdf, stacked_buckets, legend, "No entries.")

    with _pdf_card(pdf):
        count_title = f"Entries per {'day' if summary.period == ReportPeriod.WEEK else 'week'}"
        _pdf_section_heading(pdf, count_title)
        _pdf_count_line_chart(pdf, count_items, "No entries.")

    narrative, highlights = build_narrative(summary)
    with _pdf_card(pdf):
        _pdf_section_heading(pdf, "Summary")
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 6, _pdf_safe(narrative), new_x="LMARGIN", new_y="NEXT", align="L")
        pdf.ln(1)
        for highlight in highlights:
            pdf.multi_cell(
                0, 6, _pdf_safe(f"- {highlight}"), new_x="LMARGIN", new_y="NEXT", align="L"
            )

    output = pdf.output()
    return bytes(output)


@router.get("/report.pdf")
def export_report_pdf(
    db: DbDep,
    period: ReportPeriod,
    date: date | None = None,
) -> Response:
    """Download a PDF report for the week/month/quarter containing ``date``.

    Reuses ``GET /reports/summary``'s aggregation (``get_reports_summary``) — same content as
    ``GET /exports/report.html``, rendered with ``fpdf2`` (pure Python, no system libraries).
    """
    summary = get_reports_summary(db, period, date)
    pdf_bytes = _render_report_pdf(summary)
    filename = _report_filename(db, "pdf")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
