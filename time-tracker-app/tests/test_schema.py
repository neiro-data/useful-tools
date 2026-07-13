"""Tests for the SQLite schema bootstrap in ``app.schema``."""

import sqlite3

import pytest

from app.schema import init_db

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

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO entries (title, start_ts, entry_mode, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("test", "2026-07-13T10:00:00+00:00", "bogus", "now", "now"),
        )


def test_valid_entry_and_tag_can_be_linked(conn: sqlite3.Connection) -> None:
    init_db(conn)

    conn.execute(
        """
        INSERT INTO entries (title, start_ts, entry_mode, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("Deep work", "2026-07-13T10:00:00+00:00", "timer", "now", "now"),
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
