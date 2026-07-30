from __future__ import annotations

from pathlib import Path

import pytest

from config_gui.store import APP_DIR_ENV


@pytest.fixture(autouse=True)
def wtt_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Never let a test touch the real ~/.webpage-time-tracker."""
    monkeypatch.setenv(APP_DIR_ENV, str(tmp_path / "wtt"))
    return tmp_path / "wtt"
