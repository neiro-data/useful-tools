"""Unit tests for ``app.repo.read_snapshot``.

Uses a real on-disk WAL database (not ``:memory:``) because these tests need two independent
connections observing the same underlying file, which ``:memory:`` connections cannot do.
"""

import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.config import get_settings
from app.db import get_connection
from app.db_schema import init_db
from app.repo import read_snapshot


@pytest.fixture
def db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point the app at a fresh temp WAL database file and bootstrap its schema."""
    path = tmp_path / "test.db"
    monkeypatch.setenv("TIME_TRACKER_DATABASE_PATH", str(path))
    get_settings.cache_clear()

    with get_connection() as conn:
        init_db(conn)

    yield path

    get_settings.cache_clear()


def test_snapshot_isolation_from_concurrent_writer(db_path: Path) -> None:
    with get_connection() as conn_a, get_connection() as conn_b:
        with read_snapshot(conn_a):
            count_before = conn_a.execute("SELECT COUNT(*) AS n FROM categories").fetchone()["n"]

            conn_b.execute("INSERT INTO categories (name) VALUES ('Snapshot Test')")
            conn_b.commit()

            count_during = conn_a.execute("SELECT COUNT(*) AS n FROM categories").fetchone()["n"]
            assert count_during == count_before

        count_after = conn_a.execute("SELECT COUNT(*) AS n FROM categories").fetchone()["n"]
        assert count_after == count_before + 1


def test_writers_are_not_blocked_by_an_open_read_snapshot(db_path: Path) -> None:
    with get_connection() as conn_a, get_connection() as conn_b:
        with read_snapshot(conn_a):
            # Perform a read first so the snapshot is actually established.
            conn_a.execute("SELECT COUNT(*) AS n FROM categories").fetchone()

            start = time.monotonic()
            conn_b.execute("INSERT INTO categories (name) VALUES ('Writer Test')")
            conn_b.commit()
            elapsed = time.monotonic() - start

            # Regression guard: if read_snapshot ever used BEGIN IMMEDIATE (like transaction()),
            # this write would block until the 30s busy timeout instead of completing promptly.
            assert elapsed < 1.0


def test_exception_inside_block_propagates_and_leaves_no_open_transaction(db_path: Path) -> None:
    with get_connection() as conn:
        with pytest.raises(RuntimeError, match="boom"), read_snapshot(conn):
            conn.execute("SELECT COUNT(*) AS n FROM categories").fetchone()
            raise RuntimeError("boom")

        assert conn.in_transaction is False

        # A leaked read transaction under WAL would prevent a fresh BEGIN DEFERRED from
        # succeeding cleanly (or would still be "in transaction" from the failed block above).
        conn.execute("BEGIN DEFERRED")
        conn.execute("SELECT COUNT(*) AS n FROM categories").fetchone()
        conn.execute("COMMIT")


def test_successful_block_leaves_no_open_transaction(db_path: Path) -> None:
    with get_connection() as conn:
        with read_snapshot(conn):
            conn.execute("SELECT COUNT(*) AS n FROM categories").fetchone()

        assert conn.in_transaction is False


def test_nested_read_snapshot_raises_a_clear_error(db_path: Path) -> None:
    """Nesting must fail with an explicit error, not SQLite's opaque nested-transaction message.

    ``read_snapshot`` wraps an entire route handler, so a repo helper called from inside it that
    opened its own transaction would otherwise surface as
    ``cannot start a transaction within a transaction``.
    """
    with get_connection() as conn:
        conn.isolation_level = None
        with read_snapshot(conn):
            with pytest.raises(RuntimeError, match="cannot be nested"):
                with read_snapshot(conn):
                    pass  # pragma: no cover - the nested block must never execute
        assert conn.in_transaction is False
