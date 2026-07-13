"""Shared FastAPI dependencies for the resource routers under ``app/routers/``."""

import sqlite3
from collections.abc import Generator
from typing import Annotated

from fastapi import Depends

from app.db import get_connection


def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Request-scoped SQLite connection dependency.

    Wraps ``app.db.get_connection`` (a context manager) as a plain generator function, which is
    the form FastAPI's dependency injection expects for "yield" dependencies.

    ``isolation_level`` is set to ``None`` (autocommit) so route handlers have full manual control
    over transactions via ``app.repo.transaction`` — needed to close the check-then-insert race on
    the single-active-timer guard (see ``app/API_CONTRACT.md``).
    """
    with get_connection() as conn:
        conn.isolation_level = None
        yield conn


DbDep = Annotated[sqlite3.Connection, Depends(get_db)]
"""Reusable annotation for injecting a request-scoped SQLite connection into route handlers."""
