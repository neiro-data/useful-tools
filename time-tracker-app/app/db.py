"""Minimal SQLite connection helper.

TODO(schema-owner): This module intentionally does NOT define any tables or run migrations.
Schema design and migration management are owned by a later module (e.g. ``app/migrations.py``
or a dedicated migration tool). This file only provides a way to obtain a connection.
"""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager

from app.config import get_settings


def _connect() -> sqlite3.Connection:
    """Open a new SQLite connection to the configured database file.

    ``check_same_thread=False`` is required because each connection is created
    inside a sync FastAPI dependency, which Starlette may dispatch to a
    different threadpool thread than the route handler that ultimately uses
    it. This is safe here: each request gets its own connection, and that
    connection is only ever used serially within that single request's
    lifecycle (no sharing across concurrent requests). ``timeout`` sets a
    busy timeout so a connection waiting on a lock (e.g. during a concurrent
    write) retries briefly instead of immediately raising ``database is
    locked``.
    """
    settings = get_settings()
    connection = sqlite3.connect(
        settings.database_path,
        check_same_thread=False,
        timeout=30,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """Context-managed SQLite connection, suitable for use as a FastAPI dependency.

    Usage:
        with get_connection() as conn:
            conn.execute(...)
    """
    connection = _connect()
    try:
        yield connection
    finally:
        connection.close()
