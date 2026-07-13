"""``/categories`` endpoints. See ``app/API_CONTRACT.md#categories`` for the full contract."""

import sqlite3

from fastapi import APIRouter, Query

from app.deps import DbDep
from app.errors import ConflictError, NotFoundError
from app.repo import category_from_row
from app.schemas import CategoryCreate, CategoryListResponse, CategoryRead, CategoryUpdate

router = APIRouter(prefix="/categories", tags=["categories"])


def _get_category_or_404(db: sqlite3.Connection, category_id: int) -> sqlite3.Row:
    row = db.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
    if row is None:
        raise NotFoundError(
            f"Category {category_id} does not exist.", details={"category_id": category_id}
        )
    result: sqlite3.Row = row
    return result


@router.get("", response_model=CategoryListResponse)
def list_categories(
    db: DbDep,
    include_inactive: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> CategoryListResponse:
    """List categories, sorted by ``sort_order ASC, name ASC``.

    By default only active categories are returned; pass ``include_inactive=true`` to include
    deactivated ones too.
    """
    where = "" if include_inactive else "WHERE is_active = 1"
    total = db.execute(f"SELECT COUNT(*) FROM categories {where}").fetchone()[0]  # noqa: S608
    rows = db.execute(
        f"SELECT * FROM categories {where} ORDER BY sort_order ASC, name ASC LIMIT ? OFFSET ?",  # noqa: S608
        (limit, offset),
    ).fetchall()
    return CategoryListResponse(items=[category_from_row(r) for r in rows], total=total)


@router.post("", response_model=CategoryRead, status_code=201)
def create_category(payload: CategoryCreate, db: DbDep) -> CategoryRead:
    """Create a category. ``409 conflict`` if ``name`` already exists."""
    existing = db.execute("SELECT id FROM categories WHERE name = ?", (payload.name,)).fetchone()
    if existing is not None:
        raise ConflictError(
            f"Category name '{payload.name}' already exists.", details={"name": payload.name}
        )
    try:
        cur = db.execute(
            "INSERT INTO categories (name, color, sort_order) VALUES (?, ?, ?)",
            (payload.name, payload.color, payload.sort_order),
        )
    except sqlite3.IntegrityError as exc:
        raise ConflictError(
            f"Category name '{payload.name}' already exists.", details={"name": payload.name}
        ) from exc
    row = db.execute("SELECT * FROM categories WHERE id = ?", (cur.lastrowid,)).fetchone()
    return category_from_row(row)


@router.get("/{category_id}", response_model=CategoryRead)
def get_category(category_id: int, db: DbDep) -> CategoryRead:
    """Get one category by id. ``404 resource_not_found`` if it doesn't exist."""
    return category_from_row(_get_category_or_404(db, category_id))


@router.patch("/{category_id}", response_model=CategoryRead)
def update_category(category_id: int, payload: CategoryUpdate, db: DbDep) -> CategoryRead:
    """Partially update a category (only fields present in the request body are applied)."""
    row = _get_category_or_404(db, category_id)

    fields = payload.model_dump(exclude_unset=True)
    name = fields.get("name", row["name"])
    color = fields.get("color", row["color"])
    sort_order = fields.get("sort_order", row["sort_order"])
    is_active = fields.get("is_active", bool(row["is_active"]))

    if "name" in fields and name != row["name"]:
        dup = db.execute(
            "SELECT id FROM categories WHERE name = ? AND id != ?", (name, category_id)
        ).fetchone()
        if dup is not None:
            raise ConflictError(f"Category name '{name}' already exists.", details={"name": name})

    try:
        db.execute(
            "UPDATE categories SET name = ?, color = ?, sort_order = ?, is_active = ? WHERE id = ?",
            (name, color, sort_order, int(is_active), category_id),
        )
    except sqlite3.IntegrityError as exc:
        raise ConflictError(
            f"Category name '{name}' already exists.", details={"name": name}
        ) from exc

    updated = db.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
    return category_from_row(updated)


@router.post("/{category_id}/deactivate", response_model=CategoryRead)
def deactivate_category(category_id: int, db: DbDep) -> CategoryRead:
    """Idempotently set ``is_active=false`` on a category."""
    _get_category_or_404(db, category_id)
    db.execute("UPDATE categories SET is_active = 0 WHERE id = ?", (category_id,))
    updated = db.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
    return category_from_row(updated)
