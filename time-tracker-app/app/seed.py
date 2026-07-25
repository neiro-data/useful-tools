"""Declarative category seeding from a version-controlled TOML file.

Rationale
---------
Categories are the one piece of user data that is really *configuration*: a small, hand-curated
taxonomy you want to keep in version control and reproduce on a fresh database. Rather than
POSTing them one at a time, ``seed/categories.toml`` is the source of truth and this module
applies it.

Sync semantics
--------------
``categories.name`` is UNIQUE (see ``app/db_schema.py``), so it doubles as the match key for an
``ON CONFLICT`` upsert: rows in the file but not the database are inserted, rows already present
have their ``color``/``sort_order`` updated to match the file. Nothing is ever deleted, so a
category that has entries attached can never be orphaned by a re-run.

``is_active`` is deliberately **not** synced. Deactivation is UI-owned state -- syncing it would
resurrect a category the user explicitly retired via ``POST /categories/{id}/deactivate`` on the
next seed run, which is surprising and hard to undo.

Unlike ``_seed_default_settings``, this is **not** wired into ``init_db``. Because the sync
overwrites ``color``/``sort_order``, running it on every startup would revert UI edits each time
the ``--reload`` dev server restarts. It is an explicit, opt-in command instead.
"""

import argparse
import sqlite3
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from app.db import get_connection
from app.db_schema import init_db
from app.schemas import CategoryCreate

DEFAULT_SEED_PATH = Path(__file__).resolve().parent.parent / "seed" / "categories.toml"

# Top-level key in the TOML file: an array of tables, i.e. `[[category]]`.
_TABLE_KEY = "category"


class SeedError(Exception):
    """Raised when the seed file is missing, malformed, or fails validation."""


@dataclass(frozen=True)
class SyncResult:
    """Counts of what a :func:`sync_categories` call changed."""

    inserted: tuple[str, ...] = ()
    updated: tuple[str, ...] = ()

    def summary(self) -> str:
        """Human-readable one-liner, e.g. ``4 inserted, 0 updated``."""
        return f"{len(self.inserted)} inserted, {len(self.updated)} updated"


def load_seed_file(path: Path = DEFAULT_SEED_PATH) -> list[CategoryCreate]:
    """Parse and validate the TOML seed file into ``CategoryCreate`` models.

    Validation is delegated to the same pydantic model the API uses for ``POST /categories``, so
    the file is held to exactly the same rules as the endpoint (non-empty name, ``color`` at most
    32 chars, ``sort_order >= 0``).

    Raises:
        SeedError: if the file is missing, is not valid TOML, has no ``[[category]]`` entries,
            contains a duplicate name, or fails model validation.
    """
    try:
        raw = path.read_bytes()
    except FileNotFoundError as exc:
        raise SeedError(f"Seed file not found: {path}") from exc

    try:
        document = tomllib.loads(raw.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise SeedError(f"{path} is not valid TOML: {exc}") from exc

    entries = document.get(_TABLE_KEY)
    if not entries:
        raise SeedError(f"{path} defines no [[{_TABLE_KEY}]] entries.")
    if not isinstance(entries, list):
        raise SeedError(f"{path}: expected [[{_TABLE_KEY}]] to be an array of tables.")

    categories: list[CategoryCreate] = []
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise SeedError(f"{path}: [[{_TABLE_KEY}]] #{index} is not a table.")
        try:
            categories.append(CategoryCreate.model_validate(entry))
        except ValidationError as exc:
            raise SeedError(f"{path}: [[{_TABLE_KEY}]] #{index} is invalid:\n{exc}") from exc

    _reject_duplicate_names(categories, path)
    return categories


def _reject_duplicate_names(categories: list[CategoryCreate], path: Path) -> None:
    """Fail fast on duplicate names within the file.

    Left unchecked these would silently collapse: the later entry's upsert would overwrite the
    earlier one's, so the file would not describe the state it appears to.
    """
    seen: set[str] = set()
    for category in categories:
        if category.name in seen:
            raise SeedError(f"{path}: duplicate category name {category.name!r}.")
        seen.add(category.name)


def sync_categories(
    conn: sqlite3.Connection,
    categories: list[CategoryCreate],
    *,
    dry_run: bool = False,
) -> SyncResult:
    """Upsert ``categories`` into the database, matching existing rows on ``name``.

    Existing names are read up front so the result can report insert-vs-update counts, which
    ``ON CONFLICT`` alone does not expose. The whole batch runs in one transaction: if any row
    fails, nothing is written.

    Args:
        conn: Open connection to a bootstrapped database.
        categories: Validated models, typically from :func:`load_seed_file`.
        dry_run: Compute the result without writing anything.
    """
    existing = {row["name"] for row in conn.execute("SELECT name FROM categories")}

    inserted = tuple(c.name for c in categories if c.name not in existing)
    updated = tuple(c.name for c in categories if c.name in existing)
    result = SyncResult(inserted=inserted, updated=updated)

    if dry_run:
        return result

    # `is_active` is intentionally absent from the DO UPDATE clause -- see the module docstring.
    with conn:
        conn.executemany(
            """
            INSERT INTO categories (name, color, sort_order)
            VALUES (:name, :color, :sort_order)
            ON CONFLICT (name) DO UPDATE SET
                color = excluded.color,
                sort_order = excluded.sort_order
            """,
            [{"name": c.name, "color": c.color, "sort_order": c.sort_order} for c in categories],
        )
    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.seed",
        description="Apply seed/categories.toml to the time-tracker database.",
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_SEED_PATH,
        help=f"Path to the TOML seed file (default: {DEFAULT_SEED_PATH}).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without writing to the database.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entrypoint for ``uv run python -m app.seed``.

    Returns a process exit code: 0 on success, 1 if the seed file could not be loaded.
    """
    args = _build_parser().parse_args(argv)

    try:
        categories = load_seed_file(args.file)
    except SeedError as exc:
        print(f"error: {exc}", file=sys.stderr)  # noqa: T201
        return 1

    with get_connection() as conn:
        # Bootstrap first so seeding works against a database file that does not exist yet.
        init_db(conn)
        result = sync_categories(conn, categories, dry_run=args.dry_run)

    prefix = "would apply" if args.dry_run else "applied"
    print(f"{prefix}: {result.summary()} (from {args.file})")  # noqa: T201
    for name in result.inserted:
        print(f"  + {name}")  # noqa: T201
    for name in result.updated:
        print(f"  ~ {name}")  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
