"""Tests for the declarative category seeder (``app/seed.py``)."""

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.db_schema import create_schema
from app.seed import DEFAULT_SEED_PATH, SeedError, load_seed_file, sync_categories

SAMPLE_TOML = """
[[category]]
name = "Deep work"
color = "#4C6EF5"
sort_order = 10

[[category]]
name = "Meetings"
color = "#F59F00"
sort_order = 20
"""


@pytest.fixture
def conn() -> Iterator[sqlite3.Connection]:
    """An in-memory database with the real schema applied."""
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    create_schema(connection)
    try:
        yield connection
    finally:
        connection.close()


def write_toml(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "categories.toml"
    path.write_text(content, encoding="utf-8")
    return path


def read_categories(conn: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    return {row["name"]: row for row in conn.execute("SELECT * FROM categories")}


# --- Loading / validation -----------------------------------------------------------------


def test_loads_the_repo_seed_file() -> None:
    """The committed seed file must always be valid -- it ships as the default."""
    categories = load_seed_file(DEFAULT_SEED_PATH)

    assert len(categories) > 0
    assert len({c.name for c in categories}) == len(categories)


def test_missing_file_raises_seed_error(tmp_path: Path) -> None:
    with pytest.raises(SeedError, match="not found"):
        load_seed_file(tmp_path / "nope.toml")


def test_malformed_toml_raises_seed_error(tmp_path: Path) -> None:
    path = write_toml(tmp_path, "[[category]\nname = broken")

    with pytest.raises(SeedError, match="not valid TOML"):
        load_seed_file(path)


def test_empty_file_raises_seed_error(tmp_path: Path) -> None:
    path = write_toml(tmp_path, "# nothing here\n")

    with pytest.raises(SeedError, match="no \\[\\[category\\]\\] entries"):
        load_seed_file(path)


def test_duplicate_names_are_rejected(tmp_path: Path) -> None:
    """Two entries with one name would silently collapse into a single upserted row."""
    path = write_toml(
        tmp_path,
        '[[category]]\nname = "Admin"\n\n[[category]]\nname = "Admin"\ncolor = "#000000"\n',
    )

    with pytest.raises(SeedError, match="duplicate category name"):
        load_seed_file(path)


@pytest.mark.parametrize(
    "body",
    [
        pytest.param('[[category]]\nname = ""\n', id="empty-name"),
        pytest.param('[[category]]\nname = "A"\nsort_order = -1\n', id="negative-sort-order"),
        pytest.param(f'[[category]]\nname = "A"\ncolor = "{"x" * 33}"\n', id="color-too-long"),
    ],
)
def test_invalid_values_are_rejected(tmp_path: Path, body: str) -> None:
    """Validation is inherited from ``CategoryCreate``, the model the API uses."""
    path = write_toml(tmp_path, body)

    with pytest.raises(SeedError, match="is invalid"):
        load_seed_file(path)


def test_invalid_file_writes_nothing(tmp_path: Path, conn: sqlite3.Connection) -> None:
    """A malformed file must fail before any row reaches the database."""
    path = write_toml(tmp_path, '[[category]]\nname = ""\n')

    with pytest.raises(SeedError):
        load_seed_file(path)

    assert read_categories(conn) == {}


# --- Sync semantics -----------------------------------------------------------------------


def test_seeds_an_empty_database(tmp_path: Path, conn: sqlite3.Connection) -> None:
    categories = load_seed_file(write_toml(tmp_path, SAMPLE_TOML))

    result = sync_categories(conn, categories)

    assert result.inserted == ("Deep work", "Meetings")
    assert result.updated == ()
    rows = read_categories(conn)
    assert set(rows) == {"Deep work", "Meetings"}
    assert rows["Deep work"]["color"] == "#4C6EF5"
    assert rows["Deep work"]["sort_order"] == 10
    assert rows["Deep work"]["is_active"] == 1


def test_rerun_is_idempotent(tmp_path: Path, conn: sqlite3.Connection) -> None:
    categories = load_seed_file(write_toml(tmp_path, SAMPLE_TOML))
    sync_categories(conn, categories)
    before = read_categories(conn)

    result = sync_categories(conn, categories)

    assert result.inserted == ()
    assert result.updated == ("Deep work", "Meetings")
    after = read_categories(conn)
    assert set(after) == set(before)
    assert [dict(row) for row in after.values()] == [dict(row) for row in before.values()]


def test_edited_values_are_upserted(tmp_path: Path, conn: sqlite3.Connection) -> None:
    """The file is the source of truth for ``color`` and ``sort_order``."""
    sync_categories(conn, load_seed_file(write_toml(tmp_path, SAMPLE_TOML)))
    original_id = read_categories(conn)["Deep work"]["id"]

    edited = SAMPLE_TOML.replace('color = "#4C6EF5"', 'color = "#FF0000"').replace(
        "sort_order = 10", "sort_order = 99"
    )
    result = sync_categories(conn, load_seed_file(write_toml(tmp_path, edited)))

    assert result.inserted == ()
    row = read_categories(conn)["Deep work"]
    assert row["color"] == "#FF0000"
    assert row["sort_order"] == 99
    assert row["id"] == original_id, "upsert must update in place, not replace the row"


def test_new_entry_is_added_to_existing_database(tmp_path: Path, conn: sqlite3.Connection) -> None:
    sync_categories(conn, load_seed_file(write_toml(tmp_path, SAMPLE_TOML)))

    extended = SAMPLE_TOML + '\n[[category]]\nname = "Learning"\nsort_order = 30\n'
    result = sync_categories(conn, load_seed_file(write_toml(tmp_path, extended)))

    assert result.inserted == ("Learning",)
    assert len(read_categories(conn)) == 3


def test_deactivated_category_stays_deactivated(tmp_path: Path, conn: sqlite3.Connection) -> None:
    """``is_active`` is UI-owned: re-seeding must not resurrect a retired category."""
    categories = load_seed_file(write_toml(tmp_path, SAMPLE_TOML))
    sync_categories(conn, categories)
    conn.execute("UPDATE categories SET is_active = 0 WHERE name = 'Meetings'")
    conn.commit()

    sync_categories(conn, categories)

    assert read_categories(conn)["Meetings"]["is_active"] == 0


def test_sync_never_deletes_rows_absent_from_the_file(
    tmp_path: Path, conn: sqlite3.Connection
) -> None:
    """A category created in the UI must survive a seed run that does not mention it."""
    conn.execute("INSERT INTO categories (name, color) VALUES ('Ad hoc', '#111111')")
    conn.commit()

    sync_categories(conn, load_seed_file(write_toml(tmp_path, SAMPLE_TOML)))

    assert "Ad hoc" in read_categories(conn)


def test_dry_run_reports_without_writing(tmp_path: Path, conn: sqlite3.Connection) -> None:
    categories = load_seed_file(write_toml(tmp_path, SAMPLE_TOML))

    result = sync_categories(conn, categories, dry_run=True)

    assert result.inserted == ("Deep work", "Meetings")
    assert read_categories(conn) == {}


def test_summary_is_human_readable(tmp_path: Path, conn: sqlite3.Connection) -> None:
    result = sync_categories(conn, load_seed_file(write_toml(tmp_path, SAMPLE_TOML)))

    assert result.summary() == "2 inserted, 0 updated"
