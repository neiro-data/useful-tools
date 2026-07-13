"""Shared SQLite access helpers used by the ``app/routers/*`` route implementations.

Kept deliberately small and dependency-free (aside from ``app.schemas``/``app.errors``): row ->
pydantic serialization, timestamp normalization, and the category/tag existence checks shared by
several routers.
"""

import sqlite3
from collections.abc import Generator, Iterable
from contextlib import contextmanager
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from app.errors import NotFoundError
from app.schemas import CategoryRead, EntryRead, SettingsRead, TagRead

# --- Timestamps -----------------------------------------------------------------------------


def utc_now_iso() -> str:
    """Current time as an ISO-8601 UTC string, matching ``app/schema.py``'s storage format."""
    return datetime.now(UTC).isoformat()


def to_utc_iso(dt: datetime) -> str:
    """Normalize an aware ``datetime`` to its UTC ISO-8601 text representation for storage."""
    return dt.astimezone(UTC).isoformat()


def parse_ts(text: str) -> datetime:
    """Parse a stored ISO-8601 timestamp string back into an aware ``datetime``."""
    return datetime.fromisoformat(text)


def compute_duration_minutes(start: datetime, end: datetime) -> float:
    """Duration in minutes between two aware datetimes (``end`` may equal ``start``)."""
    return (end - start).total_seconds() / 60.0


def get_settings_timezone(db: sqlite3.Connection) -> str:
    """Read ``settings.timezone`` (falling back to ``"UTC"`` if no settings row exists yet)."""
    row = db.execute("SELECT timezone FROM settings LIMIT 1").fetchone()
    tz_name: str = row["timezone"] if row is not None else "UTC"
    return tz_name


def local_day_bounds_utc(tz_name: str, local_date: date) -> tuple[str, str]:
    """UTC ISO-8601 ``(start, end)`` bounds covering a single local calendar day.

    ``local_date`` is interpreted in ``tz_name`` (e.g. ``settings.timezone``); the returned bounds
    span ``[local_date 00:00:00, local_date 23:59:59.999999]`` in that timezone, converted to UTC.
    """
    return local_range_bounds_utc(tz_name, local_date, local_date)


def local_range_bounds_utc(tz_name: str, start_date: date, end_date: date) -> tuple[str, str]:
    """UTC ISO-8601 ``(start, end)`` bounds covering an inclusive local date range.

    Both ``start_date`` and ``end_date`` are interpreted in ``tz_name``; the returned bounds span
    ``[start_date 00:00:00, end_date 23:59:59.999999]`` in that timezone, converted to UTC.
    """
    tz = ZoneInfo(tz_name)
    start_local = datetime.combine(start_date, time.min, tzinfo=tz)
    end_local = datetime.combine(end_date, time.max, tzinfo=tz)
    start_utc = start_local.astimezone(UTC).isoformat()
    end_utc = end_local.astimezone(UTC).isoformat()
    return start_utc, end_utc


# --- Transactions ----------------------------------------------------------------------------


@contextmanager
def transaction(db: sqlite3.Connection) -> Generator[None, None, None]:
    """Explicit, immediate-lock transaction for multi-statement writes.

    ``db.isolation_level`` is set to ``None`` (autocommit) by ``app.deps.get_db``, so callers get
    full manual control here. ``BEGIN IMMEDIATE`` acquires the write lock up front, closing the
    race window between a guard ``SELECT`` and a subsequent ``INSERT``/``UPDATE`` (see the
    single-active-timer rule in ``app/API_CONTRACT.md``).
    """
    db.execute("BEGIN IMMEDIATE")
    try:
        yield
    except Exception:
        db.execute("ROLLBACK")
        raise
    else:
        db.execute("COMMIT")


# --- Row -> model serialization ---------------------------------------------------------------


def category_from_row(row: sqlite3.Row) -> CategoryRead:
    return CategoryRead(
        id=row["id"],
        name=row["name"],
        color=row["color"],
        is_active=bool(row["is_active"]),
        sort_order=row["sort_order"],
    )


def tag_from_row(row: sqlite3.Row) -> TagRead:
    return TagRead(id=row["id"], name=row["name"], is_active=bool(row["is_active"]))


def settings_from_row(row: sqlite3.Row) -> SettingsRead:
    return SettingsRead(
        id=row["id"],
        default_entry_mode=row["default_entry_mode"],
        week_starts_on=row["week_starts_on"],
        default_export_format=row["default_export_format"],
        database_label=row["database_label"],
        timezone=row["timezone"],
    )


def get_category_row(db: sqlite3.Connection, category_id: int) -> sqlite3.Row | None:
    result: sqlite3.Row | None = db.execute(
        "SELECT * FROM categories WHERE id = ?", (category_id,)
    ).fetchone()
    return result


def get_tags_for_entry(db: sqlite3.Connection, entry_id: int) -> list[sqlite3.Row]:
    rows: list[sqlite3.Row] = db.execute(
        """
        SELECT t.* FROM tags t
        JOIN entry_tags et ON et.tag_id = t.id
        WHERE et.entry_id = ?
        ORDER BY t.name ASC
        """,
        (entry_id,),
    ).fetchall()
    return rows


def entry_from_row(db: sqlite3.Connection, row: sqlite3.Row) -> EntryRead:
    category = None
    if row["category_id"] is not None:
        category_row = get_category_row(db, row["category_id"])
        if category_row is not None:
            category = category_from_row(category_row)

    tags = [tag_from_row(r) for r in get_tags_for_entry(db, row["id"])]

    return EntryRead(
        id=row["id"],
        title=row["title"],
        notes=row["notes"],
        category=category,
        tags=tags,
        start_ts=row["start_ts"],
        end_ts=row["end_ts"],
        duration_minutes=row["duration_minutes"],
        entry_mode=row["entry_mode"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


# --- Cross-resource validation ----------------------------------------------------------------


def validate_category_and_tags(
    db: sqlite3.Connection, category_id: int | None, tag_ids: Iterable[int]
) -> None:
    """Raise :class:`NotFoundError` if ``category_id`` or any ``tag_ids`` entry doesn't exist."""
    if category_id is not None:
        row = db.execute("SELECT id FROM categories WHERE id = ?", (category_id,)).fetchone()
        if row is None:
            raise NotFoundError(
                f"Category {category_id} does not exist.",
                details={"category_id": category_id},
            )

    unique_ids = sorted(set(tag_ids))
    if not unique_ids:
        return

    placeholders = ",".join("?" for _ in unique_ids)
    query = f"SELECT id FROM tags WHERE id IN ({placeholders})"  # noqa: S608 - placeholders only
    rows = db.execute(query, unique_ids).fetchall()
    found_ids = {r["id"] for r in rows}
    missing = [tid for tid in unique_ids if tid not in found_ids]
    if missing:
        raise NotFoundError(
            f"Tag id(s) {missing} do not exist.",
            details={"tag_ids": missing},
        )
