"""``/exports`` endpoints. See ``app/API_CONTRACT.md#exports`` for the full contract.

Three download endpoints: a full SQLite database backup, a CSV export of completed entries, and
an Outlook-pasteable HTML report (built on top of ``app/routers/reports.py``'s aggregation).
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


def _safe_filename_slug(text: str) -> str:
    """Lowercase ``text`` and collapse any run of non-alphanumeric characters into a single
    ``-``, for safe use inside a downloaded filename."""
    lowered = text.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return slug or "export"


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
                row["title"],
                category_name,
                row["start_ts"],
                row["end_ts"],
                row["duration_minutes"],
                row["entry_mode"],
                tag_names,
                row["notes"] or "",
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
    attributes and ``<table>``-based layout only (no ``<style>`` block, no external CSS, no JS)."""
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

    period_label = summary.period.value.capitalize()
    entry_word = "entry" if summary.entry_count == 1 else "entries"

    category_rows = [
        [
            escape(row.category.name) if row.category is not None else "(none)",
            format_minutes(row.total_minutes),
            str(row.entry_count),
        ]
        for row in summary.by_category
    ]
    tag_rows = [
        [escape(row.tag.name), format_minutes(row.total_minutes), str(row.entry_count)]
        for row in summary.by_tag
    ]
    day_rows = [
        [row.date.isoformat(), format_minutes(row.total_minutes), str(row.entry_count)]
        for row in summary.by_day
    ]

    body = "".join(
        [
            f'<div style="{container_style}">',
            f'<p style="{heading_style}">Time Tracker Report &mdash; {escape(period_label)}</p>',
            f'<p style="{subheading_style}">{summary.start_date.isoformat()} to '
            f"{summary.end_date.isoformat()} ({escape(summary.timezone)})</p>",
            f'<p style="{subheading_style}">Total: {format_minutes(summary.total_minutes)} '
            f"across {summary.entry_count} {entry_word}</p>",
            f'<p style="{section_heading_style}">By category</p>',
            _table(["Category", "Time", "Entries"], category_rows, "No entries."),
            f'<p style="{section_heading_style}">By tag</p>',
            _table(["Tag", "Time", "Entries"], tag_rows, "No tagged entries."),
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
