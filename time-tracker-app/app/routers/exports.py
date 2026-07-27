"""``/exports`` endpoints. See ``app/API_CONTRACT.md#exports`` for the full contract.

Download endpoints: a full SQLite database backup, a CSV export of completed entries, and
Outlook-pasteable HTML, Markdown, and PDF reports (all built on top of
``app/routers/reports.py``'s aggregation, ``get_reports_summary``).
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
from datetime import UTC, date, datetime
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
    FONT_MONO,
    FONT_SANS,
    RADIUS_PX,
    SURFACE,
    TEXT,
    TEXT_SECONDARY,
    hex_to_rgb,
    resolve_category_color,
    tag_gray,
)
from app.routers.reports import build_narrative, format_minutes, get_reports_summary
from app.schemas import ReportPeriod, ReportSummaryResponse

router = APIRouter(prefix="/exports", tags=["exports"])


def _report_filename(db: sqlite3.Connection, extension: str) -> str:
    """Build a report export filename the same way ``export_entries_csv`` does: ``<label>``
    slug + generation-date stamp."""
    label = _safe_filename_slug(_get_database_label(db))
    date_stamp = datetime.now(UTC).strftime("%Y%m%d")
    return f"{label}-report-{date_stamp}.{extension}"


def _bar_chart_title(summary: ReportSummaryResponse) -> str:
    """Title for the "how did time break down over sub-periods" chart: by day for a week report,
    by week for month/quarter reports (``by_day`` is too sparse/wide to chart at month/quarter
    granularity, so ``by_week`` — already zero-filled by ``get_reports_summary`` — is used
    instead)."""
    return "By day" if summary.period == ReportPeriod.WEEK else "By week"


def _sub_period_chart_items(summary: ReportSummaryResponse) -> list[tuple[str, int]]:
    """``(label, total_minutes)`` pairs for :func:`_bar_chart_title`'s chart, reusing
    ``summary.by_day``/``summary.by_week`` — no separate aggregation."""
    if summary.period == ReportPeriod.WEEK:
        return [(row.date.isoformat(), row.total_minutes) for row in summary.by_day]
    return [
        (f"{row.week_start.isoformat()} to {row.week_end.isoformat()}", row.total_minutes)
        for row in summary.by_week
    ]


def _category_chart_items(summary: ReportSummaryResponse) -> list[tuple[str, int, str]]:
    """``(label, total_minutes, color)`` triples, colors resolved via
    :func:`app.report_theme.resolve_category_color`."""
    return [
        (
            row.category.name if row.category is not None else "Uncategorized",
            row.total_minutes,
            resolve_category_color(row.category.color if row.category is not None else None),
        )
        for row in summary.by_category
    ]


def _tag_chart_items(summary: ReportSummaryResponse) -> list[tuple[str, int, str]]:
    """``(label, total_minutes, color)`` triples, colors from :func:`app.report_theme.tag_gray`
    (tags have no stored color, unlike categories)."""
    return [
        (row.tag.name, row.total_minutes, tag_gray(index))
        for index, row in enumerate(summary.by_tag)
    ]


@dataclass(frozen=True)
class Segment:
    """One slice of a segmented breakdown bar (category or tag), mirroring
    ``SegmentedBreakdown``'s props in ``frontend/src/components/SegmentedBreakdown``."""

    label: str
    minutes: int
    percent: float
    color: str


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


def _report_rows(
    summary: ReportSummaryResponse,
) -> tuple[list[list[str]], list[list[str]], list[list[str]]]:
    """Build the raw (un-escaped) category/tag/day row data shared by all three report renderers.

    Category/tag names come straight from user input and are returned as-is: the Markdown and PDF
    renderers use them verbatim, while the HTML renderer is responsible for calling ``escape()`` on
    them at the point of rendering. Building the rows in one place means a new breakdown field only
    needs to be added here, and keeps HTML escaping a single, visible decision instead of something
    that can be silently dropped from one of three near-duplicated comprehensions.

    Category rows carry a 4th element: the row's resolved hex color (see
    :func:`app.report_theme.resolve_category_color`), used for the color swatch column.
    """
    category_rows = [
        [
            row.category.name if row.category is not None else "Uncategorized",
            format_minutes(row.total_minutes),
            str(row.entry_count),
            resolve_category_color(row.category.color if row.category is not None else None),
        ]
        for row in summary.by_category
    ]
    tag_rows = [
        [row.tag.name, format_minutes(row.total_minutes), str(row.entry_count)]
        for row in summary.by_tag
    ]
    day_rows = [
        [row.date.isoformat(), format_minutes(row.total_minutes), str(row.entry_count)]
        for row in summary.by_day
    ]
    return category_rows, tag_rows, day_rows


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


def _count_chart_items(summary: ReportSummaryResponse) -> list[tuple[str, int]]:
    """``(label, entry_count)`` pairs for the "entries per day/week" chart, using the same buckets
    (and labels) as :func:`_sub_period_chart_items`."""
    if summary.period == ReportPeriod.WEEK:
        return [(row.date.isoformat(), row.entry_count) for row in summary.by_day]
    return [
        (f"{row.week_start.isoformat()} to {row.week_end.isoformat()}", row.entry_count)
        for row in summary.by_week
    ]


def _render_report_html(summary: ReportSummaryResponse) -> str:
    """Render ``summary`` as a self-contained, Outlook-safe HTML document: inline ``style``
    attributes and ``<table>``-based layout only (no ``<style>`` block, no external CSS, no JS,
    no SVG — Outlook strips all three). Visually mirrors the Reports page (``ReportsPage.tsx``):
    header, total card, category/tag segmented breakdowns, sub-period bar chart, entry-count
    chart, then the narrative summary."""
    container_style = f"font-family: {FONT_SANS}; color: {TEXT}; font-size: 14px;"
    heading_style = "font-size: 20px; font-weight: bold; margin: 0 0 4px 0;"
    subheading_style = f"font-size: 13px; color: {TEXT_SECONDARY}; margin: 0 0 6px 0;"
    section_heading_style = "font-size: 16px; font-weight: bold; margin: 0 0 8px 0;"
    table_style = "border-collapse: collapse; width: 100%; margin-bottom: 8px;"
    th_style = (
        f"border: 1px solid {BORDER}; background-color: {BG_SUBTLE}; padding: 6px 10px; "
        "text-align: left; font-size: 13px;"
    )
    td_style = f"border: 1px solid {BORDER}; padding: 6px 10px; font-size: 13px;"
    duration_td_style = (
        td_style + f" font-family: {FONT_MONO}; "
        "font-variant-numeric: tabular-nums; white-space: nowrap;"
    )
    bar_label_td_style = td_style + " width: 30%;"
    bar_value_td_style = duration_td_style + " width: 15%;"
    bar_cell_td_style = td_style

    def _card(inner_html: str) -> str:
        """A ``SURFACE``-filled, ``BORDER``-stroked "card" table, matching the Reports page
        card treatment. ``border-radius`` degrades to a square corner in Outlook -- fine, since
        the rest of the layout stays intact."""
        return (
            f'<table cellpadding="0" cellspacing="0" border="0" style="width: 100%; '
            f"border-collapse: separate; background-color: {SURFACE}; border: 1px solid "
            f'{BORDER}; border-radius: {RADIUS_PX}px; margin-bottom: 16px;"><tr>'
            f'<td style="padding: 16px;">{inner_html}</td></tr></table>'
        )

    def _table(headers: list[str], rows: list[list[str]], empty_message: str) -> str:
        header_cells = "".join(f'<th style="{th_style}">{escape(h)}</th>' for h in headers)
        if rows:
            body_rows = "".join(
                "<tr>" + "".join(f'<td style="{td_style}">{cell}</td>' for cell in row) + "</tr>"
                for row in rows
            )
        else:
            body_rows = (
                f'<tr><td style="{td_style}" colspan="{len(headers)}">{empty_message}</td></tr>'
            )
        return (
            f'<table style="{table_style}" cellpadding="0" cellspacing="0" border="0">'
            f"<tr>{header_cells}</tr>{body_rows}</table>"
        )

    def _category_table(rows: list[list[str]], empty_message: str) -> str:
        """Same as ``_table``, but the ``Color`` column renders a swatch ``<td>`` before the
        literal hex text (``rows``'s 4th element)."""
        headers = ["Category", "Color", "Time", "Entries"]
        header_cells = "".join(f'<th style="{th_style}">{escape(h)}</th>' for h in headers)
        if rows:
            body_rows = "".join(
                "<tr>"
                f'<td style="{td_style}">{row[0]}</td>'
                f'<td style="{td_style}">'
                f'<span style="display: inline-block; width: 10px; height: 10px; '
                f'background-color: {row[3]}; border-radius: 2px; margin-right: 6px;">'
                "&nbsp;</span>"
                f"{escape(row[3])}</td>"
                f'<td style="{duration_td_style}">{row[1]}</td>'
                f'<td style="{td_style}">{row[2]}</td>'
                "</tr>"
                for row in rows
            )
        else:
            body_rows = f'<tr><td style="{td_style}" colspan="4">{empty_message}</td></tr>'
        return (
            f'<table style="{table_style}" cellpadding="0" cellspacing="0" border="0">'
            f"<tr>{header_cells}</tr>{body_rows}</table>"
        )

    def _segmented_bar(segments: list[Segment], empty_message: str) -> str:
        """A single-row table, one ``<td>`` per segment (``width`` as both a style and an HTML
        attribute, for Outlook's non-CSS table engine), followed by a legend table (swatch,
        label, duration, rounded percent). Visible segments are floored at 1% width so a small
        share doesn't visually collapse to nothing."""
        if not segments:
            return f'<p style="{td_style} border: none;">{escape(empty_message)}</p>'
        widths = [max(1, round(segment.percent)) if segment.minutes else 0 for segment in segments]
        bar_cells = "".join(
            f'<td width="{width}%" style="background-color: {segment.color}; width: {width}%; '
            'font-size: 1px; line-height: 10px;">&nbsp;</td>'
            for segment, width in zip(segments, widths, strict=True)
            if width > 0
        )
        bar = (
            '<table cellpadding="0" cellspacing="0" border="0" '
            'style="width: 100%; border-collapse: collapse; margin-bottom: 8px;">'
            f"<tr>{bar_cells}</tr></table>"
        )
        legend_rows = "".join(
            "<tr>"
            f'<td style="{td_style} width: 16px;">'
            f'<span style="display: inline-block; width: 10px; height: 10px; '
            f'background-color: {segment.color}; border-radius: 2px;">&nbsp;</span></td>'
            f'<td style="{td_style}">{escape(segment.label)}</td>'
            f'<td style="{duration_td_style}">{format_minutes(segment.minutes)}</td>'
            f'<td style="{td_style}">{round(segment.percent)}%</td>'
            "</tr>"
            for segment in segments
        )
        legend = (
            f'<table style="{table_style}" cellpadding="0" cellspacing="0" border="0">'
            f"{legend_rows}</table>"
        )
        return bar + legend

    def _bar_chart(items: list[tuple[str, int]], bar_color: str, empty_message: str) -> str:
        """Horizontal bar chart via a nested table: each row is a label cell, a bar cell (an
        inner 2-cell table with a colored, percentage-width "filled" cell and an empty
        remainder cell), and a value cell. Outlook-safe: no ``<style>``, no SVG, no JS."""
        if not items:
            return f'<p style="{td_style} border: none;">{escape(empty_message)}</p>'
        max_value = max(value for _, value in items)
        rows_html = []
        for label, value in items:
            pct = round(100 * value / max_value) if max_value else 0
            remainder = 100 - pct
            bar_inner = (
                '<table cellpadding="0" cellspacing="0" border="0" '
                'style="width: 100%; border-collapse: collapse;"><tr>'
                f'<td width="{pct}%" style="background-color: {bar_color}; width: {pct}%; '
                f'font-size: 1px; line-height: 6px;">&nbsp;</td>'
                f'<td width="{remainder}%" style="width: {remainder}%; font-size: 1px; '
                'line-height: 6px;">&nbsp;</td>'
                "</tr></table>"
            )
            rows_html.append(
                "<tr>"
                f'<td style="{bar_label_td_style}">{escape(label)}</td>'
                f'<td style="{bar_cell_td_style}">{bar_inner}</td>'
                f'<td style="{bar_value_td_style}">{value}</td>'
                "</tr>"
            )
        return (
            f'<table style="{table_style}" cellpadding="0" cellspacing="0" border="0">'
            f"{''.join(rows_html)}</table>"
        )

    period_label = summary.period.value.capitalize()
    entry_word = "entry" if summary.entry_count == 1 else "entries"

    raw_category_rows, raw_tag_rows, day_rows = _report_rows(summary)
    # Escape here, at the point of rendering: the first column of category_rows/tag_rows is a
    # free-text name (category/tag), the rest are already-formatted numbers/strings that need no
    # escaping. The category row's 4th element (hex color) is not user-derived, so it needs no
    # escaping either.
    category_rows = [[escape(row[0]), row[1], row[2], row[3]] for row in raw_category_rows]
    tag_rows = [[escape(row[0]), *row[1:]] for row in raw_tag_rows]
    category_segments, tag_segments = _segment_items(summary)

    narrative, highlights = build_narrative(summary)

    header_card = _card(
        f'<p style="{heading_style}">Time Tracker Report &mdash; {escape(period_label)}</p>'
        f'<p style="{subheading_style}">{summary.start_date.isoformat()} to '
        f"{summary.end_date.isoformat()} ({escape(summary.timezone)})</p>"
    )

    total_card = _card(
        f'<p style="{section_heading_style}">Total time</p>'
        f'<p style="font-size: 28px; font-weight: bold; margin: 0; font-family: '
        f'{FONT_MONO}; font-variant-numeric: tabular-nums;">'
        f"{format_minutes(summary.total_minutes)}</p>"
        f'<p style="{subheading_style}">{summary.entry_count} {entry_word}</p>'
    )

    category_card = _card(
        f'<p style="{section_heading_style}">By category</p>'
        + _segmented_bar(category_segments, "No entries.")
        + _category_table(category_rows, "No entries.")
    )

    tag_card = _card(
        f'<p style="{section_heading_style}">By tag</p>'
        + _segmented_bar(tag_segments, "No tagged entries.")
        + _table(["Tag", "Time", "Entries"], tag_rows, "No tagged entries.")
    )

    sub_period_card = _card(
        f'<p style="{section_heading_style}">{escape(_bar_chart_title(summary))}</p>'
        + _bar_chart(_sub_period_chart_items(summary), ACCENT, "No entries.")
    )

    count_card = _card(
        '<p style="'
        + section_heading_style
        + '">Entries per '
        + escape("day" if summary.period == ReportPeriod.WEEK else "week")
        + "</p>"
        + _bar_chart(_count_chart_items(summary), ACCENT, "No entries.")
        + _table(["Date", "Time", "Entries"], day_rows, "No entries.")
    )

    highlights_html = "".join(f"<li>{escape(item)}</li>" for item in highlights)
    summary_card = _card(
        f'<p style="{section_heading_style}">Summary</p>'
        f'<p style="margin: 0 0 8px 0;">{escape(narrative)}</p>'
        f'<ul style="margin: 0; padding-left: 20px;">{highlights_html}</ul>'
    )

    body = "".join(
        [
            f'<div style="{container_style}">',
            header_card,
            total_card,
            category_card,
            tag_card,
            sub_period_card,
            count_card,
            summary_card,
            "</div>",
        ]
    )

    return (
        "<!DOCTYPE html>"
        '<html><head><meta charset="utf-8"></head>'
        f'<body style="margin:0; padding:16px; background-color: {BG_SUBTLE};">{body}</body>'
        "</html>"
    )


@router.get("/report.html")
def export_report_html(
    db: DbDep,
    period: ReportPeriod,
    date: date | None = None,
) -> Response:
    """View an Outlook-pasteable HTML report for the week/month/quarter containing ``date``.

    Reuses ``GET /reports/summary``'s aggregation (``get_reports_summary``) and renders it as a
    single self-contained HTML document (inline styles, table layout only). Returned inline
    (``Content-Disposition`` is not set to ``attachment``) so it renders directly in a browser.
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


def _md_table(headers: list[str], rows: list[list[str]], empty_message: str) -> str:
    if not rows:
        return f"_{empty_message}_\n"
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    lines.extend("| " + " | ".join(_md_escape(cell) for cell in row) + " |" for row in rows)
    return "\n".join(lines) + "\n"


def _md_segment_table(label_header: str, segments: list[Segment], empty_message: str) -> str:
    """Render a category/tag segmented breakdown as a Markdown table: ``| <label_header> | Color |
    Time | % | Bar |``, with a proportional ``█``/``░`` bar and the literal hex color text."""
    if not segments:
        return f"_{empty_message}_\n"
    max_percent = max(segment.percent for segment in segments)
    lines = [f"| {label_header} | Color | Time | % | Bar |", "|---|---|---|---|---|"]
    for segment in segments:
        filled = round(_MD_BAR_WIDTH * segment.percent / max_percent) if max_percent else 0
        bar = "█" * filled + "░" * (_MD_BAR_WIDTH - filled)
        lines.append(
            f"| {_md_escape(segment.label)} | {segment.color} | "
            f"{format_minutes(segment.minutes)} | {round(segment.percent)}% | `{bar}` |"
        )
    return "\n".join(lines) + "\n"


def _render_report_markdown(summary: ReportSummaryResponse) -> str:
    """Render ``summary`` as Markdown: content parity with :func:`_render_report_html` (header,
    total, category/tag breakdowns, sub-period chart, entry-count chart, narrative summary) --
    no visual restyling, no embedded raw HTML."""
    period_label = summary.period.value.capitalize()
    entry_word = "entry" if summary.entry_count == 1 else "entries"

    _category_rows, _tag_rows, day_rows = _report_rows(summary)
    category_segments, tag_segments = _segment_items(summary)
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
        _md_segment_table("Tag", tag_segments, "No tagged entries."),
        f"## {_bar_chart_title(summary)}",
        "",
        _md_bar_chart(_sub_period_chart_items(summary), "No entries."),
        f"## Entries per {'day' if summary.period == ReportPeriod.WEEK else 'week'}",
        "",
        _md_bar_chart(_count_chart_items(summary), "No entries."),
        _md_table(["Date", "Time", "Entries"], day_rows, "No entries."),
        "## Summary",
        "",
        narrative,
        "",
        *[f"- {highlight}" for highlight in highlights],
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
_PDF_BAR_LABEL_WIDTH_MM = 55.0
_PDF_BAR_VALUE_WIDTH_MM = 25.0
_PDF_BAR_MAX_WIDTH_MM = _PDF_CONTENT_WIDTH_MM - _PDF_BAR_LABEL_WIDTH_MM - _PDF_BAR_VALUE_WIDTH_MM

_PDF_BAR_LABEL_MAX_CHARS = 32
_PDF_CARD_PADDING_MM = 4.0

_PDF_BORDER_RGB = hex_to_rgb(BORDER)
_PDF_TEXT_RGB = hex_to_rgb(TEXT)
_PDF_TEXT_SECONDARY_RGB = hex_to_rgb(TEXT_SECONDARY)
_PDF_WHITE_RGB = (255, 255, 255)
_PDF_ACCENT_RGB = hex_to_rgb(ACCENT)


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


def _pdf_truncate_label(label: str, max_chars: int = _PDF_BAR_LABEL_MAX_CHARS) -> str:
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
            pdf.set_draw_color(*_PDF_BORDER_RGB)
            height = y_end - y_start + _PDF_CARD_PADDING_MM
            try:
                pdf.rect(
                    x_start,
                    y_start,
                    _PDF_CONTENT_WIDTH_MM,
                    height,
                    style="D",
                    round_corners=True,
                    corner_radius=2.0,
                )
            except TypeError:
                # Older fpdf2 without round_corners support: fall back to a square-cornered rect.
                pdf.rect(x_start, y_start, _PDF_CONTENT_WIDTH_MM, height, style="D")
        pdf.set_xy(x_start, y_end + _PDF_CARD_PADDING_MM + 6)
        _pdf_reset_colors(pdf)


def _pdf_bar_chart(
    pdf: FPDF,
    items: list[tuple[str, int, str]],
    empty_message: str = "No entries.",
    value_formatter: Callable[[int], str] = format_minutes,
) -> None:
    """Draw a horizontal bar chart as real filled rectangles (``fpdf2``'s vector drawing, not an
    image), one row per item, bar width proportional to the largest value, colored per-item."""
    if not items:
        pdf.cell(0, 6, _pdf_safe(empty_message), new_x="LMARGIN", new_y="NEXT")
        return
    max_value = max(value for _, value, _ in items)
    row_height = 6.0
    for label, value, color_hex in items:
        bar_width = (_PDF_BAR_MAX_WIDTH_MM * value / max_value) if max_value else 0.0
        x_start = pdf.get_x()
        y_start = pdf.get_y()
        pdf.cell(
            _PDF_BAR_LABEL_WIDTH_MM,
            row_height,
            _pdf_safe(_pdf_truncate_label(label)),
            new_x="RIGHT",
            new_y="TOP",
        )
        bar_x = x_start + _PDF_BAR_LABEL_WIDTH_MM
        pdf.set_fill_color(*hex_to_rgb(color_hex))
        if bar_width > 0:
            pdf.rect(bar_x, y_start + 1, bar_width, row_height - 2, style="F")
        pdf.set_fill_color(*_PDF_WHITE_RGB)
        pdf.set_xy(bar_x + _PDF_BAR_MAX_WIDTH_MM, y_start)
        pdf.cell(
            _PDF_BAR_VALUE_WIDTH_MM,
            row_height,
            _pdf_safe(value_formatter(value)),
            new_x="LMARGIN",
            new_y="NEXT",
        )


def _pdf_segmented_bar(pdf: FPDF, segments: list[Segment], empty_message: str) -> None:
    """Draw a category/tag segmented breakdown: adjacent filled rects sized by ``percent``,
    followed by a legend row (swatch, label, duration, rounded percent) per segment."""
    if not segments:
        pdf.cell(0, 6, _pdf_safe(empty_message), new_x="LMARGIN", new_y="NEXT")
        return

    bar_height = 6.0
    x_start = pdf.get_x()
    y_start = pdf.get_y()
    cursor_x = x_start
    for segment in segments:
        if not segment.minutes:
            continue
        width = max(1.0, _PDF_CONTENT_WIDTH_MM * segment.percent / 100)
        pdf.set_fill_color(*hex_to_rgb(segment.color))
        pdf.rect(cursor_x, y_start, width, bar_height, style="F")
        cursor_x += width
    pdf.set_fill_color(*_PDF_WHITE_RGB)
    pdf.set_xy(x_start, y_start + bar_height + 2)

    pdf.set_font("Helvetica", "", 9)
    for segment in segments:
        swatch_x = pdf.get_x()
        swatch_y = pdf.get_y()
        pdf.set_fill_color(*hex_to_rgb(segment.color))
        pdf.rect(swatch_x, swatch_y + 1, 3, 3, style="F")
        pdf.set_fill_color(*_PDF_WHITE_RGB)
        pdf.set_x(swatch_x + 5)
        pdf.cell(65, 5, _pdf_safe(_pdf_truncate_label(segment.label)))
        pdf.cell(30, 5, _pdf_safe(format_minutes(segment.minutes)))
        pdf.cell(20, 5, f"{round(segment.percent)}%", new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(x_start)
    pdf.set_font("Helvetica", "", 10)


def _pdf_table(pdf: FPDF, headers: list[str], rows: list[list[str]], empty_message: str) -> None:
    col_width = _PDF_CONTENT_WIDTH_MM / len(headers)
    pdf.set_font("Helvetica", "B", 10)
    for header in headers:
        pdf.cell(col_width, 7, _pdf_safe(header), border=1)
    pdf.ln(7)
    pdf.set_font("Helvetica", "", 10)
    if not rows:
        pdf.cell(
            _PDF_CONTENT_WIDTH_MM,
            7,
            _pdf_safe(empty_message),
            border=1,
            new_x="LMARGIN",
            new_y="NEXT",
        )
        return
    for row in rows:
        for cell in row:
            pdf.cell(col_width, 7, _pdf_safe(cell), border=1)
        pdf.ln(7)


def _pdf_category_table(pdf: FPDF, rows: list[list[str]], empty_message: str) -> None:
    """Same layout as :func:`_pdf_table`, but the ``Color`` column draws a filled swatch rect
    (``row``'s 4th element, a hex color) instead of the hex text."""
    headers = ["Category", "Color", "Time", "Entries"]
    col_width = _PDF_CONTENT_WIDTH_MM / len(headers)
    pdf.set_font("Helvetica", "B", 10)
    for header in headers:
        pdf.cell(col_width, 7, _pdf_safe(header), border=1)
    pdf.ln(7)
    pdf.set_font("Helvetica", "", 10)
    if not rows:
        pdf.cell(
            _PDF_CONTENT_WIDTH_MM,
            7,
            _pdf_safe(empty_message),
            border=1,
            new_x="LMARGIN",
            new_y="NEXT",
        )
        return
    for name, time_label, entry_count, color_hex in rows:
        pdf.cell(col_width, 7, _pdf_safe(name), border=1)
        swatch_x = pdf.get_x()
        swatch_y = pdf.get_y()
        pdf.cell(col_width, 7, "", border=1)
        pdf.set_fill_color(*hex_to_rgb(color_hex))
        pdf.rect(swatch_x + 3, swatch_y + 2.5, 4, 3, style="F")
        pdf.set_fill_color(*_PDF_WHITE_RGB)
        pdf.cell(col_width, 7, _pdf_safe(time_label), border=1)
        pdf.cell(col_width, 7, _pdf_safe(entry_count), border=1)
        pdf.ln(7)


def _render_report_pdf(summary: ReportSummaryResponse) -> bytes:
    """Render ``summary`` as a PDF: content/structure mirroring the Reports page (header, total
    card, category/tag segmented breakdowns, sub-period bar chart, entry-count chart, narrative
    summary), drawn with ``fpdf2`` (pure Python, no system libraries -- unlike e.g. weasyprint,
    which needs cairo/pango and is unsuitable for an offline local app)."""
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=_PDF_MARGIN_MM)
    pdf.set_margins(_PDF_MARGIN_MM, _PDF_MARGIN_MM, _PDF_MARGIN_MM)
    pdf.add_page()
    _pdf_reset_colors(pdf)

    period_label = summary.period.value.capitalize()
    entry_word = "entry" if summary.entry_count == 1 else "entries"

    with _pdf_card(pdf):
        pdf.set_font("Helvetica", "B", 18)
        pdf.cell(
            0,
            10,
            _pdf_safe(f"Time Tracker Report - {period_label}"),
            new_x="LMARGIN",
            new_y="NEXT",
        )
        pdf.set_text_color(*_PDF_TEXT_SECONDARY_RGB)
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(
            0,
            6,
            _pdf_safe(
                f"{summary.start_date.isoformat()} to {summary.end_date.isoformat()} "
                f"({summary.timezone})"
            ),
            new_x="LMARGIN",
            new_y="NEXT",
        )
        pdf.set_text_color(*_PDF_TEXT_RGB)

    with _pdf_card(pdf):
        _pdf_section_heading(pdf, "Total time")
        pdf.set_font("Helvetica", "B", 20)
        pdf.cell(
            0, 10, _pdf_safe(format_minutes(summary.total_minutes)), new_x="LMARGIN", new_y="NEXT"
        )
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*_PDF_TEXT_SECONDARY_RGB)
        pdf.cell(
            0, 6, _pdf_safe(f"{summary.entry_count} {entry_word}"), new_x="LMARGIN", new_y="NEXT"
        )
        pdf.set_text_color(*_PDF_TEXT_RGB)

    category_rows, tag_rows, day_rows = _report_rows(summary)
    category_segments, tag_segments = _segment_items(summary)

    with _pdf_card(pdf):
        _pdf_section_heading(pdf, "By category")
        _pdf_segmented_bar(pdf, category_segments, "No entries.")
        pdf.ln(2)
        _pdf_category_table(pdf, category_rows, "No entries.")

    with _pdf_card(pdf):
        _pdf_section_heading(pdf, "By tag")
        _pdf_segmented_bar(pdf, tag_segments, "No tagged entries.")
        pdf.ln(2)
        _pdf_table(pdf, ["Tag", "Time", "Entries"], tag_rows, "No tagged entries.")

    with _pdf_card(pdf):
        _pdf_section_heading(pdf, _bar_chart_title(summary))
        _pdf_bar_chart(
            pdf,
            [(label, minutes, ACCENT) for label, minutes in _sub_period_chart_items(summary)],
            "No entries.",
        )

    with _pdf_card(pdf):
        count_title = f"Entries per {'day' if summary.period == ReportPeriod.WEEK else 'week'}"
        _pdf_section_heading(pdf, count_title)
        _pdf_bar_chart(
            pdf,
            [(label, count, ACCENT) for label, count in _count_chart_items(summary)],
            "No entries.",
            value_formatter=str,
        )
        pdf.ln(2)
        _pdf_table(pdf, ["Date", "Time", "Entries"], day_rows, "No entries.")

    narrative, highlights = build_narrative(summary)
    with _pdf_card(pdf):
        _pdf_section_heading(pdf, "Summary")
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 6, _pdf_safe(narrative), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)
        for highlight in highlights:
            pdf.multi_cell(0, 6, _pdf_safe(f"- {highlight}"), new_x="LMARGIN", new_y="NEXT")

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
