"""``/entries`` endpoints. See ``app/API_CONTRACT.md#entries-manual-mode--shared-entry-operations``
for the full contract. These endpoints operate on entries of either ``entry_mode``; only creation
is manual-mode-only (timer entries are created via ``app/routers/timer.py``).
"""

import sqlite3
from datetime import date

from fastapi import APIRouter, Query

from app.deps import DbDep
from app.errors import NotFoundError, ValidationError
from app.repo import (
    compute_duration_minutes,
    entry_from_row,
    get_settings_timezone,
    local_range_bounds_utc,
    parse_ts,
    to_utc_iso,
    transaction,
    utc_now_iso,
    validate_category_and_tags,
)
from app.schemas import EntryCreateManual, EntryListResponse, EntryMode, EntryRead, EntryUpdate

router = APIRouter(prefix="/entries", tags=["entries"])


def _get_entry_or_404(db: sqlite3.Connection, entry_id: int) -> sqlite3.Row:
    row = db.execute("SELECT * FROM entries WHERE id = ?", (entry_id,)).fetchone()
    if row is None:
        raise NotFoundError(f"Entry {entry_id} does not exist.", details={"entry_id": entry_id})
    result: sqlite3.Row = row
    return result


@router.get("", response_model=EntryListResponse)
def list_entries(
    db: DbDep,
    start_date: date | None = None,
    end_date: date | None = None,
    category_id: int | None = None,
    tag_id: int | None = None,
    entry_mode: EntryMode | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> EntryListResponse:
    """List entries, filtered (AND semantics) by date range/category/tag/mode, sorted by
    ``start_ts DESC``."""
    if start_date is not None and end_date is not None and end_date < start_date:
        raise ValidationError(
            "end_date must be >= start_date",
            fields=[{"loc": ["query", "end_date"], "msg": "end_date must be >= start_date"}],
        )

    from_clause = "FROM entries"
    params: list[object] = []

    if tag_id is not None:
        from_clause += " JOIN entry_tags et ON et.entry_id = entries.id AND et.tag_id = ?"
        params.append(tag_id)

    where_clauses: list[str] = []
    tz_name = get_settings_timezone(db) if start_date is not None or end_date is not None else None
    if start_date is not None:
        start_utc, _ = local_range_bounds_utc(tz_name or "UTC", start_date, start_date)
        where_clauses.append("entries.start_ts >= ?")
        params.append(start_utc)
    if end_date is not None:
        _, end_utc = local_range_bounds_utc(tz_name or "UTC", end_date, end_date)
        where_clauses.append("entries.start_ts <= ?")
        params.append(end_utc)
    if category_id is not None:
        where_clauses.append("entries.category_id = ?")
        params.append(category_id)
    if entry_mode is not None:
        where_clauses.append("entries.entry_mode = ?")
        params.append(entry_mode.value)

    where_sql = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    total_row = db.execute(
        f"SELECT COUNT(DISTINCT entries.id) {from_clause}{where_sql}",  # noqa: S608
        params,
    ).fetchone()
    total = total_row[0]

    rows = db.execute(
        f"SELECT DISTINCT entries.* {from_clause}{where_sql} "  # noqa: S608
        "ORDER BY entries.start_ts DESC LIMIT ? OFFSET ?",
        [*params, limit, offset],
    ).fetchall()

    items = [entry_from_row(db, r) for r in rows]
    return EntryListResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=EntryRead, status_code=201)
def create_entry(payload: EntryCreateManual, db: DbDep) -> EntryRead:
    """Create a manual-mode entry (``entry_mode`` is always ``"manual"`` here).

    ``duration_minutes`` is computed server-side from ``start_ts``/``end_ts``, never trusted from
    the client.
    """
    validate_category_and_tags(db, payload.category_id, payload.tag_ids)

    start_ts = to_utc_iso(payload.start_ts)
    end_ts = to_utc_iso(payload.end_ts)
    duration = compute_duration_minutes(payload.start_ts, payload.end_ts)
    now = utc_now_iso()

    with transaction(db):
        cur = db.execute(
            """
            INSERT INTO entries (
                title, notes, category_id, start_ts, end_ts, duration_minutes, entry_mode,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 'manual', ?, ?)
            """,
            (
                payload.title,
                payload.notes,
                payload.category_id,
                start_ts,
                end_ts,
                duration,
                now,
                now,
            ),
        )
        entry_id = cur.lastrowid
        for tag_id in sorted(set(payload.tag_ids)):
            db.execute(
                "INSERT INTO entry_tags (entry_id, tag_id) VALUES (?, ?)", (entry_id, tag_id)
            )

    row = db.execute("SELECT * FROM entries WHERE id = ?", (entry_id,)).fetchone()
    return entry_from_row(db, row)


@router.get("/{entry_id}", response_model=EntryRead)
def get_entry(entry_id: int, db: DbDep) -> EntryRead:
    """Get one entry by id (either mode). ``404 resource_not_found`` if it doesn't exist."""
    return entry_from_row(db, _get_entry_or_404(db, entry_id))


@router.patch("/{entry_id}", response_model=EntryRead)
def update_entry(entry_id: int, payload: EntryUpdate, db: DbDep) -> EntryRead:
    """Partially update an entry. ``entry_mode`` is immutable after creation.

    Recomputes ``duration_minutes`` from the effective (post-patch) ``start_ts``/``end_ts`` pair;
    validates ``end_ts >= start_ts`` against that effective pair, not just the fields present in
    this request.
    """
    row = _get_entry_or_404(db, entry_id)
    fields = payload.model_dump(exclude_unset=True)

    title = fields.get("title", row["title"])
    notes = fields.get("notes", row["notes"])
    category_id = fields.get("category_id", row["category_id"])
    tag_ids: list[int] | None = fields.get("tag_ids", None)

    if "start_ts" in fields:
        if payload.start_ts is None:
            raise ValidationError(
                "start_ts cannot be null",
                fields=[{"loc": ["body", "start_ts"], "msg": "start_ts cannot be null"}],
            )
        effective_start = payload.start_ts
    else:
        effective_start = parse_ts(row["start_ts"])

    if "end_ts" in fields:
        effective_end = payload.end_ts
    else:
        effective_end = parse_ts(row["end_ts"]) if row["end_ts"] is not None else None

    if effective_end is not None and effective_end < effective_start:
        raise ValidationError(
            "end_ts must be >= start_ts",
            fields=[{"loc": ["body", "end_ts"], "msg": "end_ts must be >= start_ts"}],
        )

    validate_category_and_tags(db, category_id, tag_ids if tag_ids is not None else [])

    start_ts_str = to_utc_iso(effective_start)
    end_ts_str = to_utc_iso(effective_end) if effective_end is not None else None
    duration = (
        compute_duration_minutes(effective_start, effective_end)
        if effective_end is not None
        else None
    )
    now = utc_now_iso()

    with transaction(db):
        db.execute(
            """
            UPDATE entries
            SET title = ?, notes = ?, category_id = ?, start_ts = ?, end_ts = ?,
                duration_minutes = ?, updated_at = ?
            WHERE id = ?
            """,
            (title, notes, category_id, start_ts_str, end_ts_str, duration, now, entry_id),
        )
        if tag_ids is not None:
            db.execute("DELETE FROM entry_tags WHERE entry_id = ?", (entry_id,))
            for tag_id in sorted(set(tag_ids)):
                db.execute(
                    "INSERT INTO entry_tags (entry_id, tag_id) VALUES (?, ?)", (entry_id, tag_id)
                )

    updated = db.execute("SELECT * FROM entries WHERE id = ?", (entry_id,)).fetchone()
    return entry_from_row(db, updated)


@router.delete("/{entry_id}", status_code=204)
def delete_entry(entry_id: int, db: DbDep) -> None:
    """Hard-delete an entry (cascades to ``entry_tags`` rows)."""
    _get_entry_or_404(db, entry_id)
    db.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
