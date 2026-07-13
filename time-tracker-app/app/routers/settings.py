"""``/settings`` endpoints. See ``app/API_CONTRACT.md#settings`` for the full contract.

``settings`` is a singleton table (see ``app/schema.py``'s ``_seed_default_settings``): exactly
one row exists at all times, seeded at DB init. These endpoints only ever read or update that
single row — they never insert or delete rows.
"""

import sqlite3
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter

from app.deps import DbDep
from app.errors import ValidationError
from app.repo import settings_from_row, transaction
from app.schemas import SettingsRead, SettingsUpdate

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
