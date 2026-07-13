"""``/tags`` endpoints. See ``app/API_CONTRACT.md#tags`` for the full contract."""

import sqlite3

from fastapi import APIRouter, Query

from app.deps import DbDep
from app.errors import ConflictError, NotFoundError
from app.repo import tag_from_row
from app.schemas import TagCreate, TagListResponse, TagRead, TagUpdate

router = APIRouter(prefix="/tags", tags=["tags"])


def _get_tag_or_404(db: sqlite3.Connection, tag_id: int) -> sqlite3.Row:
    row = db.execute("SELECT * FROM tags WHERE id = ?", (tag_id,)).fetchone()
    if row is None:
        raise NotFoundError(f"Tag {tag_id} does not exist.", details={"tag_id": tag_id})
    result: sqlite3.Row = row
    return result


@router.get("", response_model=TagListResponse)
def list_tags(
    db: DbDep,
    include_inactive: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> TagListResponse:
    """List tags, sorted by ``name ASC``.

    By default only active tags are returned; pass ``include_inactive=true`` to include
    deactivated ones too.
    """
    where = "" if include_inactive else "WHERE is_active = 1"
    total = db.execute(f"SELECT COUNT(*) FROM tags {where}").fetchone()[0]  # noqa: S608
    rows = db.execute(
        f"SELECT * FROM tags {where} ORDER BY name ASC LIMIT ? OFFSET ?",  # noqa: S608
        (limit, offset),
    ).fetchall()
    return TagListResponse(items=[tag_from_row(r) for r in rows], total=total)


@router.post("", response_model=TagRead, status_code=201)
def create_tag(payload: TagCreate, db: DbDep) -> TagRead:
    """Create a tag. ``409 conflict`` if ``name`` already exists."""
    existing = db.execute("SELECT id FROM tags WHERE name = ?", (payload.name,)).fetchone()
    if existing is not None:
        raise ConflictError(
            f"Tag name '{payload.name}' already exists.", details={"name": payload.name}
        )
    try:
        cur = db.execute("INSERT INTO tags (name) VALUES (?)", (payload.name,))
    except sqlite3.IntegrityError as exc:
        raise ConflictError(
            f"Tag name '{payload.name}' already exists.", details={"name": payload.name}
        ) from exc
    row = db.execute("SELECT * FROM tags WHERE id = ?", (cur.lastrowid,)).fetchone()
    return tag_from_row(row)


@router.get("/{tag_id}", response_model=TagRead)
def get_tag(tag_id: int, db: DbDep) -> TagRead:
    """Get one tag by id. ``404 resource_not_found`` if it doesn't exist."""
    return tag_from_row(_get_tag_or_404(db, tag_id))


@router.patch("/{tag_id}", response_model=TagRead)
def update_tag(tag_id: int, payload: TagUpdate, db: DbDep) -> TagRead:
    """Partially update a tag (only fields present in the request body are applied)."""
    row = _get_tag_or_404(db, tag_id)

    fields = payload.model_dump(exclude_unset=True)
    name = fields.get("name", row["name"])
    is_active = fields.get("is_active", bool(row["is_active"]))

    if "name" in fields and name != row["name"]:
        dup = db.execute(
            "SELECT id FROM tags WHERE name = ? AND id != ?", (name, tag_id)
        ).fetchone()
        if dup is not None:
            raise ConflictError(f"Tag name '{name}' already exists.", details={"name": name})

    try:
        db.execute(
            "UPDATE tags SET name = ?, is_active = ? WHERE id = ?",
            (name, int(is_active), tag_id),
        )
    except sqlite3.IntegrityError as exc:
        raise ConflictError(f"Tag name '{name}' already exists.", details={"name": name}) from exc

    updated = db.execute("SELECT * FROM tags WHERE id = ?", (tag_id,)).fetchone()
    return tag_from_row(updated)


@router.post("/{tag_id}/deactivate", response_model=TagRead)
def deactivate_tag(tag_id: int, db: DbDep) -> TagRead:
    """Idempotently set ``is_active=false`` on a tag."""
    _get_tag_or_404(db, tag_id)
    db.execute("UPDATE tags SET is_active = 0 WHERE id = ?", (tag_id,))
    updated = db.execute("SELECT * FROM tags WHERE id = ?", (tag_id,)).fetchone()
    return tag_from_row(updated)
