"""Schema definition and idempotent migration/bootstrap for the time-tracker SQLite database.

This is the **storage** layer: SQL DDL, indexes, and migrations describing how data is persisted.
Not to be confused with ``app/schemas.py``, the **wire** layer (Pydantic models describing what the
HTTP API accepts and returns). The two are enforced independently — e.g. ``entries.category_id`` is
``NOT NULL`` here *and* required in ``schemas.EntryCreateManual`` there.

Design notes
------------
- **Timestamps are stored as ISO-8601 TEXT in UTC** (e.g. ``2026-07-13T14:30:00+00:00``). This is
  the simplest, most portable choice for SQLite: it sorts lexicographically the same as
  chronologically, survives round-trips through CSV/JSON/Markdown exports without a driver-specific
  binary format, and avoids SQLite's lack of a native datetime type. Callers are responsible for
  normalizing to UTC before writing and for localizing on display (see ``settings.timezone``).
- **Foreign keys are enforced** via ``PRAGMA foreign_keys = ON`` (already applied by
  ``app/db.py``'s connection helper); this module also sets it defensively on any connection it is
  given, since SQLite requires the pragma to be set per-connection.
- **Enum-like columns** (``entries.entry_mode``, ``report_exports.report_type``,
  ``report_exports.format``) are constrained with ``CHECK`` clauses rather than a separate lookup
  table, since the value sets are small, fixed, and app-defined (not user-editable data).
- All DDL uses ``IF NOT EXISTS`` so ``init_db`` / ``create_schema`` can be called repeatedly
  (on every app startup) without side effects.
"""

import sqlite3
from pathlib import Path

from app.config import get_settings
from app.db import _connect

# --- Table DDL ---------------------------------------------------------------------------------

_CREATE_CATEGORIES = """
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    color TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0
);
"""

_CREATE_TAGS = """
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    is_active INTEGER NOT NULL DEFAULT 1
);
"""

_CREATE_ENTRIES = """
CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    notes TEXT,
    category_id INTEGER NOT NULL REFERENCES categories (id) ON DELETE RESTRICT,
    start_ts TEXT NOT NULL,
    end_ts TEXT,
    duration_minutes REAL,
    entry_mode TEXT NOT NULL CHECK (entry_mode IN ('timer', 'manual')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

_CREATE_ENTRY_TAGS = """
CREATE TABLE IF NOT EXISTS entry_tags (
    entry_id INTEGER NOT NULL REFERENCES entries (id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags (id) ON DELETE CASCADE,
    PRIMARY KEY (entry_id, tag_id)
);
"""

_CREATE_REPORT_EXPORTS = """
CREATE TABLE IF NOT EXISTS report_exports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_type TEXT NOT NULL CHECK (report_type IN ('weekly', 'monthly', 'quarterly')),
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    format TEXT NOT NULL CHECK (format IN ('html', 'csv', 'pdf', 'md')),
    created_at TEXT NOT NULL,
    file_path TEXT NOT NULL
);
"""

_CREATE_SETTINGS = """
CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    default_entry_mode TEXT NOT NULL CHECK (default_entry_mode IN ('timer', 'manual')),
    week_starts_on TEXT NOT NULL,
    default_export_format TEXT NOT NULL
        CHECK (default_export_format IN ('html', 'csv', 'pdf', 'md')),
    database_label TEXT NOT NULL,
    timezone TEXT NOT NULL
);
"""

_CREATE_TABLES = (
    _CREATE_CATEGORIES,
    _CREATE_TAGS,
    _CREATE_ENTRIES,
    _CREATE_ENTRY_TAGS,
    _CREATE_REPORT_EXPORTS,
    _CREATE_SETTINGS,
)

# --- Indexes ------------------------------------------------------------------------------------
# Tuned for the app's expected access patterns: dashboard/report date-range scans, category
# filtering, and tag-based lookups/joins.

_CREATE_INDEXES = (
    # Date-range scans: reports (weekly/monthly/quarterly) and the "current/recent entries" view
    # both filter and sort by start_ts. This is the single hottest access pattern in the app.
    "CREATE INDEX IF NOT EXISTS idx_entries_start_ts ON entries (start_ts);",
    # Filtering entries by category (e.g. "show all time logged to Category X"). Also supports
    # the FK lookup used when cascading category deactivation checks.
    "CREATE INDEX IF NOT EXISTS idx_entries_category_id ON entries (category_id);",
    # entry_tags is keyed (entry_id, tag_id) via its PK, which already indexes entry_id first.
    # A separate index on tag_id supports the reverse direction: "find all entries with tag Y",
    # used by tag-filtered reports/dashboards.
    "CREATE INDEX IF NOT EXISTS idx_entry_tags_tag_id ON entry_tags (tag_id);",
)


def create_schema(conn: sqlite3.Connection) -> None:
    """Create all tables and indexes if they do not already exist (idempotent)."""
    conn.execute("PRAGMA foreign_keys = ON")
    for statement in _CREATE_TABLES:
        conn.execute(statement)
    for statement in _CREATE_INDEXES:
        conn.execute(statement)
    conn.commit()


def _seed_default_settings(conn: sqlite3.Connection) -> None:
    """Insert a single default ``settings`` row if the table is empty."""
    row = conn.execute("SELECT COUNT(*) FROM settings").fetchone()
    if row[0] > 0:
        return

    settings = get_settings()
    conn.execute(
        """
        INSERT INTO settings (
            default_entry_mode, week_starts_on, default_export_format, database_label, timezone
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        ("timer", "monday", "md", settings.app_name, "UTC"),
    )
    conn.commit()


def _entries_category_id_is_not_null(conn: sqlite3.Connection) -> bool:
    """Whether the current ``entries`` table already has ``category_id NOT NULL``.

    Returns ``True`` for a brand-new DB too (the table is created via ``_CREATE_ENTRIES``, which
    already has the constraint), which is what makes :func:`_migrate_entries_category_not_null`
    a no-op in that case.
    """
    rows = conn.execute("PRAGMA table_info(entries)").fetchall()
    for row in rows:
        # PRAGMA table_info columns: cid, name, type, notnull, dflt_value, pk
        if row["name"] == "category_id":
            return bool(row["notnull"])
    # No entries table at all yet (fresh DB, before create_schema runs) - nothing to migrate.
    return True


def _migrate_entries_category_not_null(conn: sqlite3.Connection) -> None:
    """Idempotently rebuild ``entries`` so ``category_id`` is ``NOT NULL``.

    Old databases created before this migration have ``category_id INTEGER REFERENCES categories
    (id) ON DELETE SET NULL`` (nullable). This performs the standard SQLite 12-step table rebuild:
    create ``entries_new`` with the new (NOT NULL) DDL, copy over every row that already has a
    category, drop the old table, rename the new one into place, and recreate the indexes that get
    dropped along with the old table. Rows with ``category_id IS NULL`` cannot satisfy the new
    constraint and are discarded (along with their ``entry_tags`` rows) - the user has explicitly
    authorized destroying uncategorized entries here.

    A no-op if ``entries.category_id`` is already ``NOT NULL`` (including on a brand-new DB, where
    ``create_schema`` already created it that way), and safe to call on every startup.
    """
    if _entries_category_id_is_not_null(conn):
        return

    discarded_row = conn.execute(
        "SELECT COUNT(*) FROM entries WHERE category_id IS NULL"
    ).fetchone()
    discarded = discarded_row[0]

    # Take explicit, manual control of the transaction (rather than relying on the sqlite3
    # module's implicit-transaction default) so PRAGMA foreign_keys=OFF (which SQLite only
    # honors outside of a transaction) and the multi-statement rebuild below behave predictably
    # regardless of what isolation_level this connection happens to have been opened with.
    previous_isolation_level = conn.isolation_level
    conn.isolation_level = None

    # The rebuild must run with FK enforcement off (dropping/renaming tables mid-flight would
    # otherwise trip FK checks), and restored afterwards. Must be set outside any transaction.
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                """
                CREATE TABLE entries_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    notes TEXT,
                    category_id INTEGER NOT NULL REFERENCES categories (id) ON DELETE RESTRICT,
                    start_ts TEXT NOT NULL,
                    end_ts TEXT,
                    duration_minutes REAL,
                    entry_mode TEXT NOT NULL CHECK (entry_mode IN ('timer', 'manual')),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            # Drop entry_tags rows belonging to entries that will be discarded, then the entries
            # themselves are simply never copied over (WHERE category_id IS NOT NULL below).
            conn.execute(
                """
                DELETE FROM entry_tags
                WHERE entry_id IN (SELECT id FROM entries WHERE category_id IS NULL)
                """
            )
            conn.execute(
                """
                INSERT INTO entries_new (
                    id, title, notes, category_id, start_ts, end_ts, duration_minutes,
                    entry_mode, created_at, updated_at
                )
                SELECT
                    id, title, notes, category_id, start_ts, end_ts, duration_minutes,
                    entry_mode, created_at, updated_at
                FROM entries
                WHERE category_id IS NOT NULL
                """
            )
            conn.execute("DROP TABLE entries")
            conn.execute("ALTER TABLE entries_new RENAME TO entries")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_entries_start_ts ON entries (start_ts);")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_entries_category_id ON entries (category_id);"
            )
        except Exception:
            conn.execute("ROLLBACK")
            raise
        else:
            conn.execute("COMMIT")
    finally:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.isolation_level = previous_isolation_level

    if discarded:
        print(  # noqa: T201
            f"[migration] discarded {discarded} entries with no category "
            "(category_id is now NOT NULL)"
        )


def init_db(conn: sqlite3.Connection) -> None:
    """Idempotently bootstrap the database: create schema, migrate, then seed defaults.

    Safe to call on every application startup.
    """
    create_schema(conn)
    _migrate_entries_category_not_null(conn)
    _seed_default_settings(conn)


def _default_db_path() -> Path:
    return Path(get_settings().database_path)


def main() -> None:
    """Standalone entrypoint: ``uv run python -m app.db_schema``.

    Initializes the database file configured via ``TIME_TRACKER_DATABASE_PATH`` (or the default
    ``time_tracker.db`` in the current working directory).
    """
    conn = _connect()
    try:
        init_db(conn)
    finally:
        conn.close()
    print(f"Initialized time-tracker database at: {_default_db_path()}")  # noqa: T201


if __name__ == "__main__":
    main()
