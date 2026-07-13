"""``/timer`` endpoints. See ``app/API_CONTRACT.md#timer`` for the full contract, including the
single-active-timer rule.
"""

from fastapi import APIRouter

from app.deps import DbDep
from app.errors import ConflictError
from app.repo import (
    compute_duration_minutes,
    entry_from_row,
    parse_ts,
    transaction,
    utc_now_iso,
    validate_category_and_tags,
)
from app.schemas import EntryRead, TimerCurrentResponse, TimerStartRequest, TimerStopRequest

router = APIRouter(prefix="/timer", tags=["timer"])


@router.post("/start", response_model=EntryRead, status_code=201)
def start_timer(payload: TimerStartRequest, db: DbDep) -> EntryRead:
    """Start a new running timer (``entry_mode="timer"``, ``start_ts=now()``, ``end_ts=NULL``).

    ``409 timer_already_running`` (with ``details.running_entry_id``) if a timer is already
    active. The guard check and the insert run inside a single ``BEGIN IMMEDIATE`` transaction
    (see ``app.repo.transaction``) to close the race between them.
    """
    with transaction(db):
        running = db.execute("SELECT id FROM entries WHERE end_ts IS NULL").fetchone()
        if running is not None:
            raise ConflictError(
                f"A timer is already running (entry_id={running['id']}). Stop it before "
                "starting another.",
                code="timer_already_running",
                details={"running_entry_id": running["id"]},
            )

        validate_category_and_tags(db, payload.category_id, payload.tag_ids)

        title = payload.title or "Untitled"
        now = utc_now_iso()
        cur = db.execute(
            """
            INSERT INTO entries (
                title, notes, category_id, start_ts, end_ts, duration_minutes, entry_mode,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, NULL, NULL, 'timer', ?, ?)
            """,
            (title, payload.notes, payload.category_id, now, now, now),
        )
        entry_id = cur.lastrowid
        for tag_id in sorted(set(payload.tag_ids)):
            db.execute(
                "INSERT INTO entry_tags (entry_id, tag_id) VALUES (?, ?)", (entry_id, tag_id)
            )

    row = db.execute("SELECT * FROM entries WHERE id = ?", (entry_id,)).fetchone()
    return entry_from_row(db, row)


@router.get("/current", response_model=TimerCurrentResponse)
def get_current_timer(db: DbDep) -> TimerCurrentResponse:
    """Return the currently-running timer, if any. Always ``200`` — "no timer running" is a
    normal state, not an error."""
    row = db.execute("SELECT * FROM entries WHERE end_ts IS NULL").fetchone()
    if row is None:
        return TimerCurrentResponse(running=False, entry=None)
    return TimerCurrentResponse(running=True, entry=entry_from_row(db, row))


@router.post("/stop", response_model=EntryRead)
def stop_timer(payload: TimerStopRequest, db: DbDep) -> EntryRead:
    """Stop the running timer: sets ``end_ts=now()``, computes ``duration_minutes``, and applies
    any fields provided in ``payload``.

    ``409 no_running_timer`` if no timer is currently active.
    """
    with transaction(db):
        row = db.execute("SELECT * FROM entries WHERE end_ts IS NULL").fetchone()
        if row is None:
            raise ConflictError("No timer is currently running.", code="no_running_timer")
        entry_id = row["id"]

        fields = payload.model_dump(exclude_unset=True)
        title = fields.get("title", row["title"])
        notes = fields.get("notes", row["notes"])
        category_id = fields.get("category_id", row["category_id"])
        tag_ids: list[int] | None = fields.get("tag_ids", None)

        validate_category_and_tags(db, category_id, tag_ids if tag_ids is not None else [])

        start_ts = parse_ts(row["start_ts"])
        end_ts = utc_now_iso()
        duration = compute_duration_minutes(start_ts, parse_ts(end_ts))
        now = utc_now_iso()

        db.execute(
            """
            UPDATE entries
            SET title = ?, notes = ?, category_id = ?, end_ts = ?, duration_minutes = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (title, notes, category_id, end_ts, duration, now, entry_id),
        )
        if tag_ids is not None:
            db.execute("DELETE FROM entry_tags WHERE entry_id = ?", (entry_id,))
            for tag_id in sorted(set(tag_ids)):
                db.execute(
                    "INSERT INTO entry_tags (entry_id, tag_id) VALUES (?, ?)", (entry_id, tag_id)
                )

    updated = db.execute("SELECT * FROM entries WHERE id = ?", (entry_id,)).fetchone()
    return entry_from_row(db, updated)
