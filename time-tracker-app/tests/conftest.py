"""Shared pytest fixtures for the Phase 1 API test suite."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """A ``TestClient`` wired to a fresh, isolated SQLite file per test.

    Sets ``TIME_TRACKER_DATABASE_PATH`` to a temp file and clears the cached ``Settings`` before
    entering the app's lifespan (which calls ``init_db``), so each test starts from an empty,
    freshly-bootstrapped database.
    """
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("TIME_TRACKER_DATABASE_PATH", str(db_path))
    get_settings.cache_clear()

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client

    get_settings.cache_clear()
