"""Where the config lives on disk, and how it is read and written."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from config_gui.models import Config, ConfigError

APP_DIR_ENV = "WTT_HOME"


def app_dir() -> Path:
    """`~/.webpage-time-tracker`, overridable so tests never touch the real one."""
    override = os.environ.get(APP_DIR_ENV)
    path = Path(override) if override else Path.home() / ".webpage-time-tracker"
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_path() -> Path:
    return app_dir() / "config.json"


def icons_dir() -> Path:
    path = app_dir() / "icons"
    path.mkdir(parents=True, exist_ok=True)
    return path


def load() -> Config:
    """The stored config, or defaults if there is none / it is unreadable."""
    path = config_path()
    if not path.exists():
        return Config()
    try:
        return Config.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, ConfigError):
        return Config()


def save(config: Config) -> Path:
    """Write atomically — the server may read this file mid-write otherwise."""
    config.validated()
    path = config_path()
    payload = json.dumps(config.to_dict(), indent=2) + "\n"
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".config-", suffix=".json")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return path
