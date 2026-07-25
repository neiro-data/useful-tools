"""Tests for the SQLite schema bootstrap in ``app.db_schema``."""

import sqlite3

import pytest

from app.db_schema import init_db

EXPECTED_TABLES = {
    "entries",
    "categories",
    "tags",
    "entry_tags",
    "report_exports",
    "settings",
}

EXPECTED_INDEXES = {
    "idx_entries_start_ts",
    "idx_entries_category_id",
    "idx_entry_tags_tag_id",
}


@pytest.fixture
def conn() -> sqlite3.Connection:
    """A fresh in-memory SQLite connection with foreign keys enabled."""
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def test_init_db_creates_all_expected_tables(conn: sqlite3.Connection) -> None:
    init_db(conn)

    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    table_names = {row["name"] for row in rows}

    assert EXPECTED_TABLES <= table_names


def test_init_db_creates_expected_indexes(conn: sqlite3.Connection) -> None:
    init_db(conn)

    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    index_names = {row["name"] for row in rows}

    assert EXPECTED_INDEXES <= index_names


def test_init_db_is_idempotent(conn: sqlite3.Connection) -> None:
    init_db(conn)
    init_db(conn)  # should not raise, and should not duplicate the settings row

    count = conn.execute("SELECT COUNT(*) AS c FROM settings").fetchone()["c"]

    assert count == 1


def test_init_db_seeds_default_settings_row(conn: sqlite3.Connection) -> None:
    init_db(conn)

    row = conn.execute("SELECT * FROM settings").fetchone()

    assert row is not None
    assert row["default_entry_mode"] in ("timer", "manual")
    assert row["week_starts_on"]
    assert row["default_export_format"]
    assert row["timezone"]


def test_foreign_keys_are_enforced_on_entry_tags(conn: sqlite3.Connection) -> None:
    init_db(conn)

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO entry_tags (entry_id, tag_id) VALUES (?, ?)",
            (9999, 9999),
        )


def test_entry_mode_check_constraint_rejects_invalid_value(conn: sqlite3.Connection) -> None:
    init_db(conn)
    conn.execute("INSERT INTO categories (name) VALUES (?)", ("Deep Work",))
    category_id = conn.execute("SELECT id FROM categories").fetchone()["id"]

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO entries (title, category_id, start_ts, entry_mode, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("test", category_id, "2026-07-13T10:00:00+00:00", "bogus", "now", "now"),
        )


def test_entries_category_id_is_not_null(conn: sqlite3.Connection) -> None:
    init_db(conn)

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO entries (title, start_ts, entry_mode, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("test", "2026-07-13T10:00:00+00:00", "timer", "now", "now"),
        )


def test_valid_entry_and_tag_can_be_linked(conn: sqlite3.Connection) -> None:
    init_db(conn)

    conn.execute("INSERT INTO categories (name) VALUES (?)", ("Deep Work",))
    category_id = conn.execute("SELECT id FROM categories").fetchone()["id"]

    conn.execute(
        """
        INSERT INTO entries (title, category_id, start_ts, entry_mode, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("Deep work", category_id, "2026-07-13T10:00:00+00:00", "timer", "now", "now"),
    )
    conn.execute("INSERT INTO tags (name) VALUES (?)", ("focus",))

    entry_id = conn.execute("SELECT id FROM entries").fetchone()["id"]
    tag_id = conn.execute("SELECT id FROM tags").fetchone()["id"]

    conn.execute(
        "INSERT INTO entry_tags (entry_id, tag_id) VALUES (?, ?)",
        (entry_id, tag_id),
    )
    conn.commit()

    linked = conn.execute("SELECT COUNT(*) AS c FROM entry_tags").fetchone()["c"]

    assert linked == 1


# --- category_id NOT NULL migration ------------------------------------------------------------


def _create_old_shape_entries_table(conn: sqlite3.Connection) -> None:
    """Recreate the pre-migration schema shape: ``entries.category_id`` nullable."""
    conn.execute(
        """
        CREATE TABLE categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            color TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            is_active INTEGER NOT NULL DEFAULT 1
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            notes TEXT,
            category_id INTEGER REFERENCES categories (id) ON DELETE SET NULL,
            start_ts TEXT NOT NULL,
            end_ts TEXT,
            duration_minutes REAL,
            entry_mode TEXT NOT NULL CHECK (entry_mode IN ('timer', 'manual')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE entry_tags (
            entry_id INTEGER NOT NULL REFERENCES entries (id) ON DELETE CASCADE,
            tag_id INTEGER NOT NULL REFERENCES tags (id) ON DELETE CASCADE,
            PRIMARY KEY (entry_id, tag_id)
        )
        """
    )
    conn.execute("CREATE INDEX idx_entries_start_ts ON entries (start_ts)")
    conn.execute("CREATE INDEX idx_entries_category_id ON entries (category_id)")
    conn.execute("CREATE INDEX idx_entry_tags_tag_id ON entry_tags (tag_id)")
    conn.commit()


def test_migration_discards_null_category_rows_and_keeps_categorized_ones(
    conn: sqlite3.Connection,
) -> None:
    _create_old_shape_entries_table(conn)

    conn.execute("INSERT INTO categories (name) VALUES ('Deep Work')")
    category_id = conn.execute("SELECT id FROM categories").fetchone()["id"]
    conn.execute("INSERT INTO tags (name) VALUES ('focus')")
    tag_id = conn.execute("SELECT id FROM tags").fetchone()["id"]

    conn.execute(
        """
        INSERT INTO entries (title, category_id, start_ts, entry_mode, created_at, updated_at)
        VALUES ('Categorized', ?, '2026-07-13T10:00:00+00:00', 'manual', 'now', 'now')
        """,
        (category_id,),
    )
    categorized_id = conn.execute("SELECT id FROM entries WHERE title = 'Categorized'").fetchone()[
        "id"
    ]
    conn.execute(
        "INSERT INTO entry_tags (entry_id, tag_id) VALUES (?, ?)", (categorized_id, tag_id)
    )

    conn.execute(
        """
        INSERT INTO entries (title, category_id, start_ts, entry_mode, created_at, updated_at)
        VALUES ('Uncategorized', NULL, '2026-07-13T11:00:00+00:00', 'manual', 'now', 'now')
        """
    )
    uncategorized_id = conn.execute(
        "SELECT id FROM entries WHERE title = 'Uncategorized'"
    ).fetchone()["id"]
    conn.execute(
        "INSERT INTO entry_tags (entry_id, tag_id) VALUES (?, ?)", (uncategorized_id, tag_id)
    )
    conn.commit()

    init_db(conn)

    remaining_ids = {row["id"] for row in conn.execute("SELECT id FROM entries").fetchall()}
    assert remaining_ids == {categorized_id}

    notnull_row = conn.execute("PRAGMA table_info(entries)").fetchall()
    category_col = next(r for r in notnull_row if r["name"] == "category_id")
    assert category_col["notnull"] == 1

    remaining_tag_links = conn.execute("SELECT entry_id FROM entry_tags").fetchall()
    assert {row["entry_id"] for row in remaining_tag_links} == {categorized_id}

    index_names = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    }
    assert EXPECTED_INDEXES <= index_names


def test_migration_is_idempotent_when_run_twice(conn: sqlite3.Connection) -> None:
    _create_old_shape_entries_table(conn)
    conn.execute("INSERT INTO categories (name) VALUES ('Deep Work')")
    category_id = conn.execute("SELECT id FROM categories").fetchone()["id"]
    conn.execute(
        """
        INSERT INTO entries (title, category_id, start_ts, entry_mode, created_at, updated_at)
        VALUES ('Categorized', ?, '2026-07-13T10:00:00+00:00', 'manual', 'now', 'now')
        """,
        (category_id,),
    )
    conn.commit()

    init_db(conn)
    first_ids = {row["id"] for row in conn.execute("SELECT id FROM entries").fetchall()}

    init_db(conn)  # second run must be a no-op: no error, no data loss/duplication
    second_ids = {row["id"] for row in conn.execute("SELECT id FROM entries").fetchall()}

    assert first_ids == second_ids
    count = conn.execute("SELECT COUNT(*) AS c FROM entries").fetchone()["c"]
    assert count == 1


def test_migration_is_noop_on_brand_new_db(conn: sqlite3.Connection) -> None:
    """A fresh DB (created straight from ``_CREATE_ENTRIES``) already has the NOT NULL
    constraint, so the migration must not touch it."""
    init_db(conn)

    notnull_row = conn.execute("PRAGMA table_info(entries)").fetchall()
    category_col = next(r for r in notnull_row if r["name"] == "category_id")
    assert category_col["notnull"] == 1

    init_db(conn)  # still a no-op
    count = conn.execute("SELECT COUNT(*) AS c FROM entries").fetchone()["c"]
    assert count == 0
