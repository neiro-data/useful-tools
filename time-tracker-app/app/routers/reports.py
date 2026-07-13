"""``/reports`` endpoints. See ``app/API_CONTRACT.md#reports-summary-aggregation`` for the full
contract.
"""

import calendar
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter

from app.deps import DbDep
from app.repo import category_from_row, get_settings_timezone, local_range_bounds_utc, tag_from_row
from app.schemas import (
    ReportCategoryBreakdown,
    ReportDayBreakdown,
    ReportPeriod,
    ReportSummaryResponse,
    ReportTagBreakdown,
)

router = APIRouter(prefix="/reports", tags=["reports"])


@dataclass
class _Bucket:
    """Running total for one grouping key (category id, tag id, or local day)."""

    total_minutes: int = 0
    entry_count: int = 0

    def add(self, duration_minutes: int) -> None:
        self.total_minutes += duration_minutes
        self.entry_count += 1


@dataclass
class _TagBucket(_Bucket):
    tag_row: sqlite3.Row | None = field(default=None)


@dataclass
class _DayBucket(_Bucket):
    local_date: date = date.min


def _resolve_period_bounds(period: ReportPeriod, anchor: date) -> tuple[date, date]:
    """Resolve the local, inclusive ``(start_date, end_date)`` for the period containing
    ``anchor``."""
    if period == ReportPeriod.WEEK:
        start = anchor - timedelta(days=anchor.weekday())
        end = start + timedelta(days=6)
        return start, end

    if period == ReportPeriod.MONTH:
        start = anchor.replace(day=1)
        _, last_day = calendar.monthrange(anchor.year, anchor.month)
        end = anchor.replace(day=last_day)
        return start, end

    # ReportPeriod.QUARTER
    quarter_index = (anchor.month - 1) // 3
    start_month = quarter_index * 3 + 1
    end_month = start_month + 2
    start = date(anchor.year, start_month, 1)
    _, last_day = calendar.monthrange(anchor.year, end_month)
    end = date(anchor.year, end_month, last_day)
    return start, end


def _fetch_completed_entries(
    db: sqlite3.Connection, start_utc: str, end_utc: str
) -> list[sqlite3.Row]:
    rows: list[sqlite3.Row] = db.execute(
        """
        SELECT * FROM entries
        WHERE start_ts >= ? AND start_ts <= ? AND end_ts IS NOT NULL
        ORDER BY start_ts ASC
        """,
        (start_utc, end_utc),
    ).fetchall()
    return rows


@router.get("/summary", response_model=ReportSummaryResponse)
def get_reports_summary(
    db: DbDep,
    period: ReportPeriod,
    date: date | None = None,
) -> ReportSummaryResponse:
    """Aggregate completed entries over the ``week``/``month``/``quarter`` containing ``date``
    (defaults to today in ``settings.timezone``).

    Only entries with ``end_ts IS NOT NULL`` are included (consistent with ``/today``). Every
    duration/sum is computed server-side from stored ``duration_minutes`` values, never trusted
    from the client. An entry linked to multiple tags contributes its full duration to each of
    those tags in ``by_tag`` (so ``by_tag`` totals may double-count minutes across tags);
    ``by_day`` only includes local days that have at least one completed entry.
    """
    tz_name = get_settings_timezone(db)
    tz = ZoneInfo(tz_name)
    anchor = date if date is not None else datetime.now(tz).date()

    start_date, end_date = _resolve_period_bounds(period, anchor)
    start_utc, end_utc = local_range_bounds_utc(tz_name, start_date, end_date)

    entry_rows = _fetch_completed_entries(db, start_utc, end_utc)

    total_minutes = 0
    by_category: dict[int | None, _Bucket] = {}
    by_tag: dict[int, _TagBucket] = {}
    by_day: dict[str, _DayBucket] = {}

    for row in entry_rows:
        duration = round(row["duration_minutes"] or 0)
        total_minutes += duration

        category_id = row["category_id"]
        by_category.setdefault(category_id, _Bucket()).add(duration)

        tag_rows = db.execute(
            """
            SELECT t.* FROM tags t
            JOIN entry_tags et ON et.tag_id = t.id
            WHERE et.entry_id = ?
            """,
            (row["id"],),
        ).fetchall()
        for tag_row in tag_rows:
            by_tag.setdefault(tag_row["id"], _TagBucket(tag_row=tag_row)).add(duration)

        local_date = datetime.fromisoformat(row["start_ts"]).astimezone(tz).date()
        by_day.setdefault(local_date.isoformat(), _DayBucket(local_date=local_date)).add(duration)

    category_breakdown = [
        ReportCategoryBreakdown(
            category=(
                category_from_row(
                    db.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
                )
                if category_id is not None
                else None
            ),
            total_minutes=bucket.total_minutes,
            entry_count=bucket.entry_count,
        )
        for category_id, bucket in by_category.items()
    ]
    category_breakdown.sort(key=lambda item: item.total_minutes, reverse=True)

    tag_breakdown = [
        ReportTagBreakdown(
            tag=tag_from_row(bucket.tag_row),
            total_minutes=bucket.total_minutes,
            entry_count=bucket.entry_count,
        )
        for bucket in by_tag.values()
        if bucket.tag_row is not None
    ]
    tag_breakdown.sort(key=lambda item: item.total_minutes, reverse=True)

    day_breakdown = [
        ReportDayBreakdown(
            date=bucket.local_date,
            total_minutes=bucket.total_minutes,
            entry_count=bucket.entry_count,
        )
        for bucket in sorted(by_day.values(), key=lambda item: item.local_date)
    ]

    return ReportSummaryResponse(
        period=period,
        start_date=start_date,
        end_date=end_date,
        timezone=tz_name,
        total_minutes=total_minutes,
        entry_count=len(entry_rows),
        by_category=category_breakdown,
        by_tag=tag_breakdown,
        by_day=day_breakdown,
    )
