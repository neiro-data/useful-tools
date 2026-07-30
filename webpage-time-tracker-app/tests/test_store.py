from __future__ import annotations

import json
from pathlib import Path

import pytest

from config_gui import store
from config_gui.models import Config, ConfigError, Site


def test_load_returns_defaults_when_nothing_is_stored() -> None:
    assert store.load() == Config()


def test_save_then_load_round_trips() -> None:
    config = Config(sites=[Site.from_domain("Hacker News", "news.ycombinator.com", 20)])
    store.save(config)
    assert store.load() == config


def test_save_is_atomic_and_leaves_no_temp_files(wtt_home: Path) -> None:
    store.save(Config())
    assert json.loads(store.config_path().read_text())["version"] == 1
    assert [p.name for p in wtt_home.iterdir() if p.name.startswith(".config-")] == []


def test_save_refuses_an_invalid_config() -> None:
    with pytest.raises(ConfigError):
        store.save(Config(day_start_hour=42))
    assert not store.config_path().exists()


def test_load_falls_back_on_a_corrupt_file() -> None:
    store.config_path().write_text("{ not json", encoding="utf-8")
    assert store.load() == Config()
