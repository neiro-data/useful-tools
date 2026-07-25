"""Tests for the disposable sample-data generator (``app/dummy_data.py``).

The generator's job is to be *safe* and *repeatable*: it must never write over a real database,
and the same arguments must always produce the same content. Both are covered here, alongside the
shape of what it writes.
"""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.db_schema import init_db
from app.dummy_data import (
    DUMMY_DATABASE_LABEL,
    DummyDataError,
    assert_safe_target,
    generate,
    main,
    read_database_label,
)

# A fixed Wednesday, so the weekday/weekend split in generated data is deterministic.
NOW = datetime(2026, 7, 15, 17, 30, tzinfo=UTC)


def _rows(path: Path, sql: str) -> list[sqlite3.Row]:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        return list(conn.execute(sql))
    finally:
        conn.close()


def _count(path: Path, table: str) -> int:
    # S608: `table` is a hard-coded literal at every call site in this file, never user input.
    return int(_rows(path, f"SELECT COUNT(*) AS n FROM {table}")[0]["n"])  # noqa: S608


def test_generate_writes_a_populated_database(tmp_path: Path) -> None:
    db_path = tmp_path / "dummy.db"

    result = generate(db_path, days=14, now=NOW)

    assert db_path.exists()
    assert result.categories > 0
    assert result.tags > 0
    assert result.entries > 0
    assert _count(db_path, "entries") == result.entries
    assert _count(db_path, "tags") == result.tags


def test_generated_database_is_branded_as_dummy(tmp_path: Path) -> None:
    db_path = tmp_path / "dummy.db"

    generate(db_path, days=7, now=NOW)

    assert read_database_label(db_path) == DUMMY_DATABASE_LABEL


def test_generation_is_deterministic_for_a_given_seed(tmp_path: Path) -> None:
    first = tmp_path / "a.db"
    second = tmp_path / "b.db"

    generate(first, days=14, seed=42, now=NOW)
    generate(second, days=14, seed=42, now=NOW)

    query = "SELECT title, category_id, start_ts, end_ts FROM entries ORDER BY id"
    assert [tuple(row) for row in _rows(first, query)] == [
        tuple(row) for row in _rows(second, query)
    ]


def test_different_seeds_produce_different_data(tmp_path: Path) -> None:
    first = tmp_path / "a.db"
    second = tmp_path / "b.db"

    generate(first, days=14, seed=1, now=NOW)
    generate(second, days=14, seed=2, now=NOW)

    query = "SELECT title, start_ts FROM entries ORDER BY id"
    assert [tuple(row) for row in _rows(first, query)] != [
        tuple(row) for row in _rows(second, query)
    ]


def test_rerunning_replaces_data_instead_of_stacking(tmp_path: Path) -> None:
    db_path = tmp_path / "dummy.db"

    first = generate(db_path, days=14, now=NOW)
    second = generate(db_path, days=14, now=NOW)

    assert first.entries == second.entries
    assert _count(db_path, "entries") == second.entries
    assert _count(db_path, "tags") == second.tags


def test_entries_are_closed_and_land_on_weekdays_only(tmp_path: Path) -> None:
    db_path = tmp_path / "dummy.db"

    generate(db_path, days=21, now=NOW)

    rows = _rows(db_path, "SELECT start_ts, end_ts, duration_minutes FROM entries")
    assert rows, "expected the generator to write entries"
    for row in rows:
        assert row["end_ts"] is not None
        assert row["duration_minutes"] > 0
        assert datetime.fromisoformat(row["start_ts"]).weekday() < 5


def test_entries_stay_in_the_past(tmp_path: Path) -> None:
    db_path = tmp_path / "dummy.db"

    generate(db_path, days=21, now=NOW)

    latest = _rows(db_path, "SELECT MAX(end_ts) AS latest FROM entries")[0]["latest"]
    assert datetime.fromisoformat(latest) < NOW


def test_running_timer_flag_leaves_one_open_entry(tmp_path: Path) -> None:
    db_path = tmp_path / "dummy.db"

    generate(db_path, days=7, running_timer=True, now=NOW)

    open_entries = _rows(db_path, "SELECT id FROM entries WHERE end_ts IS NULL")
    assert len(open_entries) == 1


def test_no_running_timer_by_default(tmp_path: Path) -> None:
    db_path = tmp_path / "dummy.db"

    generate(db_path, days=7, now=NOW)

    assert _rows(db_path, "SELECT id FROM entries WHERE end_ts IS NULL") == []


def test_refuses_to_overwrite_a_real_database(tmp_path: Path) -> None:
    real_db = tmp_path / "time_tracker.db"
    conn = sqlite3.connect(real_db)
    conn.row_factory = sqlite3.Row
    try:
        init_db(conn)
    finally:
        conn.close()

    with pytest.raises(DummyDataError, match="real time-tracker database"):
        assert_safe_target(real_db)

    with pytest.raises(DummyDataError, match="real time-tracker database"):
        generate(real_db, days=7, now=NOW)


def test_refuses_a_file_that_is_not_a_time_tracker_database(tmp_path: Path) -> None:
    stray = tmp_path / "notes.db"
    stray.write_text("definitely not sqlite")

    with pytest.raises(DummyDataError):
        assert_safe_target(stray)


def test_missing_or_empty_target_is_safe(tmp_path: Path) -> None:
    missing = tmp_path / "nope.db"
    empty = tmp_path / "empty.db"
    empty.touch()

    assert read_database_label(missing) is None
    assert read_database_label(empty) is None
    assert_safe_target(missing)
    assert_safe_target(empty)


def test_cli_writes_to_the_requested_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path = tmp_path / "dummy.db"

    exit_code = main(["--path", str(db_path), "--days", "7"])

    assert exit_code == 0
    assert db_path.exists()
    assert "TIME_TRACKER_DATABASE_PATH" in capsys.readouterr().out


def test_cli_reset_rebuilds_the_file(tmp_path: Path) -> None:
    db_path = tmp_path / "dummy.db"
    main(["--path", str(db_path), "--days", "7"])

    assert main(["--path", str(db_path), "--days", "7", "--reset"]) == 0
    assert db_path.exists()
    assert read_database_label(db_path) == DUMMY_DATABASE_LABEL


def test_cli_refuses_a_real_database(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    real_db = tmp_path / "time_tracker.db"
    conn = sqlite3.connect(real_db)
    conn.row_factory = sqlite3.Row
    try:
        init_db(conn)
    finally:
        conn.close()
    before = _count(real_db, "settings")

    exit_code = main(["--path", str(real_db), "--reset"])

    assert exit_code == 1
    assert "Refusing to overwrite" in capsys.readouterr().err
    assert real_db.exists()
    assert _count(real_db, "settings") == before
