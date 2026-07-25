"""``/settings`` endpoints. See ``app/API_CONTRACT.md#settings`` for the full contract.

``settings`` is a singleton table (see ``app/db_schema.py``'s ``_seed_default_settings``): exactly
one row exists at all times, seeded at DB init. These endpoints only ever read or update that
single row — they never insert or delete rows.
"""

import sqlite3
from datetime import UTC, datetime
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from fastapi import APIRouter

from app.deps import DbDep
from app.errors import ValidationError
from app.repo import settings_from_row, transaction
from app.schemas import (
    SettingsRead,
    SettingsUpdate,
    TimezoneListResponse,
    TimezoneOption,
)

router = APIRouter(prefix="/settings", tags=["settings"])

# Fixed allowlist of mutable columns, used to build the dynamic UPDATE below. Column names never
# come from user input — only values are parameterized from this fixed set.
_MUTABLE_COLUMNS = (
    "default_entry_mode",
    "week_starts_on",
    "default_export_format",
    "database_label",
    "timezone",
)


def _get_settings_row(db: sqlite3.Connection) -> sqlite3.Row:
    row: sqlite3.Row | None = db.execute("SELECT * FROM settings LIMIT 1").fetchone()
    assert row is not None, "settings table must always contain exactly one row"  # noqa: S101
    return row


@lru_cache(maxsize=1)
def _sorted_timezone_names() -> tuple[str, ...]:
    """All IANA zone names known to ``zoneinfo``, sorted. Cached: the tz database is loaded from
    disk at process start and does not change while the app is running. Offsets are deliberately
    NOT cached here — see :func:`_format_utc_offset`."""
    return tuple(sorted(available_timezones()))


def _format_utc_offset(now_utc: datetime, name: str) -> str:
    """Format ``name``'s CURRENT offset as ``+HH:MM`` / ``-HH:MM``.

    Computed per request rather than cached because a zone's offset changes when it enters or
    leaves daylight saving time; a cached label would silently drift by an hour twice a year.
    """
    offset = now_utc.astimezone(ZoneInfo(name)).utcoffset()
    total_minutes = round(offset.total_seconds() / 60) if offset is not None else 0
    sign = "-" if total_minutes < 0 else "+"
    hours, minutes = divmod(abs(total_minutes), 60)
    return f"{sign}{hours:02d}:{minutes:02d}"


def _validate_timezone(value: str) -> None:
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise ValidationError(
            f"Unknown timezone: {value}",
            fields=[{"loc": ["body", "timezone"], "msg": f"Unknown timezone: {value}"}],
        ) from exc


@router.get("", response_model=SettingsRead)
def get_settings_endpoint(db: DbDep) -> SettingsRead:
    """Get the current (singleton) settings row."""
    return settings_from_row(_get_settings_row(db))


@router.get("/timezones", response_model=TimezoneListResponse)
def list_timezones() -> TimezoneListResponse:
    """List every timezone ``PATCH /settings`` accepts, each with its current UTC offset.

    Backs the Settings timezone dropdown. Drawn from the same ``zoneinfo`` database that
    :func:`_validate_timezone` checks against, so the UI can never offer a value the server would
    reject. Takes no database dependency — this is static process data, not app state.
    """
    now_utc = datetime.now(UTC)
    items = [
        TimezoneOption(name=name, utc_offset=_format_utc_offset(now_utc, name))
        for name in _sorted_timezone_names()
    ]
    return TimezoneListResponse(items=items, total=len(items))


@router.patch("", response_model=SettingsRead)
def update_settings(payload: SettingsUpdate, db: DbDep) -> SettingsRead:
    """Partially update the singleton settings row.

    Only fields explicitly present in the request body are applied (``exclude_unset`` semantics).
    An empty body is a no-op that returns the current settings unchanged. ``timezone`` must be a
    valid IANA zone name (validated against ``zoneinfo``) since it drives day-boundary math
    elsewhere (``/today``, ``/reports/summary``, date-range filtering on ``/entries``).
    """
    row = _get_settings_row(db)
    fields = payload.model_dump(exclude_unset=True)

    if "timezone" in fields:
        _validate_timezone(fields["timezone"])

    if not fields:
        return settings_from_row(row)

    set_clause = ", ".join(f"{col} = ?" for col in _MUTABLE_COLUMNS if col in fields)
    values = [fields[col] for col in _MUTABLE_COLUMNS if col in fields]

    with transaction(db):
        db.execute(
            f"UPDATE settings SET {set_clause} WHERE id = ?",  # noqa: S608 - fixed allowlist only
            (*values, row["id"]),
        )

    updated = _get_settings_row(db)
    return settings_from_row(updated)
