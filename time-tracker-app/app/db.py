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
    """Open a new SQLite connection to the configured database file."""
    settings = get_settings()
    connection = sqlite3.connect(settings.database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
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
