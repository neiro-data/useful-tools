from __future__ import annotations

import json
from pathlib import Path

import pytest

from html_to_epub_server.config import DEFAULT_PORT, ConfigError, load_or_create_config


def test_first_run_creates_config_with_defaults_and_token(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"

    config = load_or_create_config(config_path)

    assert config_path.exists()
    assert config.port == DEFAULT_PORT
    assert config.token
    assert len(config.token) >= 20


def test_second_load_reuses_existing_token(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    first = load_or_create_config(config_path)

    second = load_or_create_config(config_path)

    assert second.token == first.token
    assert second.output_dir == first.output_dir


def test_malformed_json_raises_clear_error(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(ConfigError, match="not valid JSON"):
        load_or_create_config(config_path)


def test_unknown_field_raises_clear_error(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"bogus_field": 1}), encoding="utf-8")

    with pytest.raises(ConfigError, match="unknown field"):
        load_or_create_config(config_path)


def test_invalid_split_level_raises_clear_error(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"output_dir": str(tmp_path), "token": "x", "split_level": 3}),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="split_level"):
        load_or_create_config(config_path)
