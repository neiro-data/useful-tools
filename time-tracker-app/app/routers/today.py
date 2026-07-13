"""``/today`` endpoint. See ``app/API_CONTRACT.md#today-convenience-aggregation`` for the full
contract.
"""

from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

from fastapi import APIRouter

from app.deps import DbDep
from app.repo import category_from_row, entry_from_row, tag_from_row
from app.schemas import TodayResponse

router = APIRouter(tags=["today"])

_RECENT_CATEGORIES_LIMIT = 5
_RECENT_TAGS_LIMIT = 8


@router.get("/today", response_model=TodayResponse)
def get_today(db: DbDep) -> TodayResponse:
    """Aggregate today's entries, the running timer (if any), and recently-used
    categories/tags for the Today screen, in one round trip.

    "Today" is resolved server-side using ``settings.timezone``; see ``app/API_CONTRACT.md`` for
    the exact boundary rule.
    """
    settings_row = db.execute("SELECT timezone FROM settings LIMIT 1").fetchone()
    tz_name = settings_row["timezone"] if settings_row is not None else "UTC"
    tz = ZoneInfo(tz_name)

    today_local = datetime.now(tz).date()
    start_local = datetime.combine(today_local, time.min, tzinfo=tz)
    end_local = datetime.combine(today_local, time.max, tzinfo=tz)
    start_utc = start_local.astimezone(UTC).isoformat()
    end_utc = end_local.astimezone(UTC).isoformat()

    entry_rows = db.execute(
        """
        SELECT * FROM entries
        WHERE start_ts >= ? AND start_ts <= ? AND end_ts IS NOT NULL
        ORDER BY start_ts DESC
        """,
        (start_utc, end_utc),
    ).fetchall()
    entries = [entry_from_row(db, row) for row in entry_rows]

    running_row = db.execute("SELECT * FROM entries WHERE end_ts IS NULL").fetchone()
    running_timer = entry_from_row(db, running_row) if running_row is not None else None

    recent_category_rows = db.execute(
        """
        SELECT c.* FROM categories c
        JOIN entries e ON e.category_id = c.id
        WHERE c.is_active = 1
        GROUP BY c.id
        ORDER BY MAX(e.start_ts) DESC
        LIMIT ?
        """,
        (_RECENT_CATEGORIES_LIMIT,),
    ).fetchall()
    recent_categories = [category_from_row(row) for row in recent_category_rows]

    recent_tag_rows = db.execute(
        """
        SELECT t.* FROM tags t
        JOIN entry_tags et ON et.tag_id = t.id
        JOIN entries e ON e.id = et.entry_id
        WHERE t.is_active = 1
        GROUP BY t.id
        ORDER BY MAX(e.start_ts) DESC
        LIMIT ?
        """,
        (_RECENT_TAGS_LIMIT,),
    ).fetchall()
    recent_tags = [tag_from_row(row) for row in recent_tag_rows]

    return TodayResponse(
        entries=entries,
        running_timer=running_timer,
        recent_categories=recent_categories,
        recent_tags=recent_tags,
    )
