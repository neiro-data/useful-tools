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
from app.routers.reports import format_minutes, get_reports_summary
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


def _category_chart_items(summary: ReportSummaryResponse) -> list[tuple[str, int]]:
    return [
        (row.category.name if row.category is not None else "(none)", row.total_minutes)
        for row in summary.by_category
    ]


def _tag_chart_items(summary: ReportSummaryResponse) -> list[tuple[str, int]]:
    return [(row.tag.name, row.total_minutes) for row in summary.by_tag]


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
    """
    category_rows = [
        [
            row.category.name if row.category is not None else "(none)",
            format_minutes(row.total_minutes),
            str(row.entry_count),
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


def _render_report_html(summary: ReportSummaryResponse) -> str:
    """Render ``summary`` as a self-contained, Outlook-safe HTML document: inline ``style``
    attributes and ``<table>``-based layout only (no ``<style>`` block, no external CSS, no JS,
    no SVG — Outlook strips all three)."""
    container_style = "font-family: Arial, Helvetica, sans-serif; color: #1a1a1a; font-size: 14px;"
    heading_style = "font-size: 20px; font-weight: bold; margin: 0 0 4px 0;"
    subheading_style = "font-size: 13px; color: #555555; margin: 0 0 6px 0;"
    section_heading_style = "font-size: 16px; font-weight: bold; margin: 24px 0 8px 0;"
    table_style = "border-collapse: collapse; width: 100%; margin-bottom: 8px;"
    th_style = (
        "border: 1px solid #cccccc; background-color: #f2f2f2; padding: 6px 10px; "
        "text-align: left; font-size: 13px;"
    )
    td_style = "border: 1px solid #cccccc; padding: 6px 10px; font-size: 13px;"
    bar_label_td_style = td_style + " width: 30%;"
    bar_value_td_style = td_style + " width: 15%; white-space: nowrap;"
    bar_cell_td_style = td_style

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

    def _bar_chart(items: list[tuple[str, int]], bar_color: str, empty_message: str) -> str:
        """Horizontal bar chart via a nested table: each row is a label cell, a bar cell (an
        inner 2-cell table with a colored, percentage-width "filled" cell and an empty
        remainder cell), and a value cell. Outlook-safe: no ``<style>``, no SVG, no JS."""
        if not items:
            return f'<p style="{td_style} border: none;">{escape(empty_message)}</p>'
        max_minutes = max(minutes for _, minutes in items)
        rows_html = []
        for label, minutes in items:
            pct = round(100 * minutes / max_minutes) if max_minutes else 0
            remainder = 100 - pct
            bar_inner = (
                '<table cellpadding="0" cellspacing="0" border="0" '
                'style="width: 100%; border-collapse: collapse;"><tr>'
                f'<td style="background-color: {bar_color}; width: {pct}%; '
                f'font-size: 1px; line-height: 6px;">&nbsp;</td>'
                f'<td style="width: {remainder}%; font-size: 1px; line-height: 6px;">&nbsp;</td>'
                "</tr></table>"
            )
            rows_html.append(
                "<tr>"
                f'<td style="{bar_label_td_style}">{escape(label)}</td>'
                f'<td style="{bar_cell_td_style}">{bar_inner}</td>'
                f'<td style="{bar_value_td_style}">{format_minutes(minutes)}</td>'
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
    # escaping.
    category_rows = [[escape(row[0]), *row[1:]] for row in raw_category_rows]
    tag_rows = [[escape(row[0]), *row[1:]] for row in raw_tag_rows]

    body = "".join(
        [
            f'<div style="{container_style}">',
            f'<p style="{heading_style}">Time Tracker Report &mdash; {escape(period_label)}</p>',
            f'<p style="{subheading_style}">{summary.start_date.isoformat()} to '
            f"{summary.end_date.isoformat()} ({escape(summary.timezone)})</p>",
            f'<p style="{subheading_style}">Total: {format_minutes(summary.total_minutes)} '
            f"across {summary.entry_count} {entry_word}</p>",
            f'<p style="{section_heading_style}">{escape(_bar_chart_title(summary))}</p>',
            _bar_chart(_sub_period_chart_items(summary), "#4C6EF5", "No entries."),
            f'<p style="{section_heading_style}">By category</p>',
            _table(["Category", "Time", "Entries"], category_rows, "No entries."),
            _bar_chart(_category_chart_items(summary), "#37B24D", "No entries."),
            f'<p style="{section_heading_style}">By tag</p>',
            _table(["Tag", "Time", "Entries"], tag_rows, "No tagged entries."),
            _bar_chart(_tag_chart_items(summary), "#F59F00", "No tagged entries."),
            f'<p style="{section_heading_style}">By day</p>',
            _table(["Date", "Time", "Entries"], day_rows, "No entries."),
            "</div>",
        ]
    )

    return (
        "<!DOCTYPE html>"
        '<html><head><meta charset="utf-8"></head>'
        f'<body style="margin:0; padding:16px;">{body}</body></html>'
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


def _md_bar_chart(items: list[tuple[str, int]], empty_message: str) -> str:
    """Render ``items`` as a Markdown table with ``█`` block-character bars proportional to the
    largest value."""
    if not items:
        return f"_{empty_message}_\n"
    max_minutes = max(minutes for _, minutes in items)
    lines = ["| | | Time |", "|---|---|---|"]
    for label, minutes in items:
        filled = round(_MD_BAR_WIDTH * minutes / max_minutes) if max_minutes else 0
        bar = "█" * filled + "░" * (_MD_BAR_WIDTH - filled)
        lines.append(f"| {label} | `{bar}` | {format_minutes(minutes)} |")
    return "\n".join(lines) + "\n"


def _md_table(headers: list[str], rows: list[list[str]], empty_message: str) -> str:
    if not rows:
        return f"_{empty_message}_\n"
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines) + "\n"


def _render_report_markdown(summary: ReportSummaryResponse) -> str:
    """Render ``summary`` as Markdown: the same content/structure as
    :func:`_render_report_html` (headline, three bar charts, three tables), as Markdown tables
    with ``█`` block-character bars instead of HTML."""
    period_label = summary.period.value.capitalize()
    entry_word = "entry" if summary.entry_count == 1 else "entries"

    category_rows, tag_rows, day_rows = _report_rows(summary)

    sections = [
        f"# Time Tracker Report — {period_label}",
        "",
        f"{summary.start_date.isoformat()} to {summary.end_date.isoformat()} ({summary.timezone})",
        "",
        f"**Total:** {format_minutes(summary.total_minutes)} across {summary.entry_count} "
        f"{entry_word}",
        "",
        f"## {_bar_chart_title(summary)}",
        "",
        _md_bar_chart(_sub_period_chart_items(summary), "No entries."),
        "## By category",
        "",
        _md_table(["Category", "Time", "Entries"], category_rows, "No entries."),
        _md_bar_chart(_category_chart_items(summary), "No entries."),
        "## By tag",
        "",
        _md_table(["Tag", "Time", "Entries"], tag_rows, "No tagged entries."),
        _md_bar_chart(_tag_chart_items(summary), "No tagged entries."),
        "## By day",
        "",
        _md_table(["Date", "Time", "Entries"], day_rows, "No entries."),
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


def _pdf_section_heading(pdf: FPDF, text: str) -> None:
    pdf.set_font("Helvetica", "B", 13)
    pdf.ln(4)
    pdf.cell(0, 8, _pdf_safe(text), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)


def _pdf_bar_chart(pdf: FPDF, items: list[tuple[str, int]], color: tuple[int, int, int]) -> None:
    """Draw a horizontal bar chart as real filled rectangles (``fpdf2``'s vector drawing, not an
    image), one row per item, bar width proportional to the largest value."""
    if not items:
        pdf.cell(0, 6, _pdf_safe("No entries."), new_x="LMARGIN", new_y="NEXT")
        return
    max_minutes = max(minutes for _, minutes in items)
    row_height = 6.0
    for label, minutes in items:
        bar_width = (_PDF_BAR_MAX_WIDTH_MM * minutes / max_minutes) if max_minutes else 0.0
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
        pdf.set_fill_color(*color)
        if bar_width > 0:
            pdf.rect(bar_x, y_start + 1, bar_width, row_height - 2, style="F")
        pdf.set_xy(bar_x + _PDF_BAR_MAX_WIDTH_MM, y_start)
        pdf.cell(
            _PDF_BAR_VALUE_WIDTH_MM,
            row_height,
            format_minutes(minutes),
            new_x="LMARGIN",
            new_y="NEXT",
        )


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


def _render_report_pdf(summary: ReportSummaryResponse) -> bytes:
    """Render ``summary`` as a PDF: the same content/structure as :func:`_render_report_html`
    (headline, three bar charts, three tables), drawn with ``fpdf2`` (pure Python, no system
    libraries — unlike e.g. weasyprint, which needs cairo/pango and is unsuitable for an offline
    local app)."""
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=_PDF_MARGIN_MM)
    pdf.set_margins(_PDF_MARGIN_MM, _PDF_MARGIN_MM, _PDF_MARGIN_MM)
    pdf.add_page()

    period_label = summary.period.value.capitalize()
    entry_word = "entry" if summary.entry_count == 1 else "entries"

    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(
        0, 10, _pdf_safe(f"Time Tracker Report - {period_label}"), new_x="LMARGIN", new_y="NEXT"
    )
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
    pdf.cell(
        0,
        6,
        _pdf_safe(
            f"Total: {format_minutes(summary.total_minutes)} across {summary.entry_count} "
            f"{entry_word}"
        ),
        new_x="LMARGIN",
        new_y="NEXT",
    )

    category_rows, tag_rows, day_rows = _report_rows(summary)

    _pdf_section_heading(pdf, _bar_chart_title(summary))
    _pdf_bar_chart(pdf, _sub_period_chart_items(summary), (76, 110, 245))

    _pdf_section_heading(pdf, "By category")
    _pdf_table(pdf, ["Category", "Time", "Entries"], category_rows, "No entries.")
    pdf.ln(2)
    _pdf_bar_chart(pdf, _category_chart_items(summary), (55, 178, 77))

    _pdf_section_heading(pdf, "By tag")
    _pdf_table(pdf, ["Tag", "Time", "Entries"], tag_rows, "No tagged entries.")
    pdf.ln(2)
    _pdf_bar_chart(pdf, _tag_chart_items(summary), (245, 159, 0))

    _pdf_section_heading(pdf, "By day")
    _pdf_table(pdf, ["Date", "Time", "Entries"], day_rows, "No entries.")

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
