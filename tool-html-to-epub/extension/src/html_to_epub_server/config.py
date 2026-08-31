"""Server configuration: load-or-create ~/.config/html-to-epub-extension/config.json."""

from __future__ import annotations

import json
import secrets
from dataclasses import asdict, dataclass, replace
from pathlib import Path

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "html-to-epub-extension"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.json"
DEFAULT_PORT = 8765
DEFAULT_FILENAME_TEMPLATE = "{date}-{slug}.epub"


class ConfigError(Exception):
    """Raised when the config file exists but cannot be parsed or is invalid."""


@dataclass(frozen=True)
class ServerConfig:
    """Resolved server configuration."""

    output_dir: str
    port: int = DEFAULT_PORT
    token: str = ""
    split_level: int = 1
    language: str = "en"
    filename_template: str = DEFAULT_FILENAME_TEMPLATE
    overwrite: bool = False

    def __post_init__(self) -> None:
        if self.split_level not in (1, 2):
            raise ConfigError("split_level must be 1 or 2")
        if not self.token:
            raise ConfigError("token must not be empty")
        if self.port < 0:
            raise ConfigError("port must be a non-negative integer (0 means OS-assigned)")


def _default_config() -> ServerConfig:
    return ServerConfig(
        output_dir=str(Path.home() / "Documents" / "html-to-epub-output"),
        port=DEFAULT_PORT,
        token=secrets.token_urlsafe(32),
        split_level=1,
        language="en",
        filename_template=DEFAULT_FILENAME_TEMPLATE,
        overwrite=False,
    )


def load_or_create_config(config_path: Path = DEFAULT_CONFIG_PATH) -> ServerConfig:
    """Load config from disk, creating it with sane defaults on first run.

    Raises:
        ConfigError: if the file exists but contains malformed JSON or invalid fields.
    """
    if not config_path.exists():
        config = _default_config()
        save_config(config, config_path)
        return config

    try:
        raw = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"could not read config file {config_path}: {exc}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"config file {config_path} is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError(f"config file {config_path} must contain a JSON object")

    defaults = asdict(_default_config())
    # Preserve any generated token only if the file omits it; unknown keys are rejected below
    # to catch typos early rather than silently ignoring them.
    known_keys = set(defaults)
    unknown = set(data) - known_keys
    if unknown:
        raise ConfigError(f"config file {config_path} has unknown field(s): {sorted(unknown)}")

    merged = {**defaults, **data}
    try:
        return ServerConfig(**merged)
    except TypeError as exc:
        raise ConfigError(f"config file {config_path} has invalid field(s): {exc}") from exc


def save_config(config: ServerConfig, config_path: Path = DEFAULT_CONFIG_PATH) -> None:
    """Write the config to disk, creating parent directories as needed."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(asdict(config), indent=2) + "\n", encoding="utf-8")


def with_output_dir(config: ServerConfig, output_dir: str) -> ServerConfig:
    """Return a copy of config with a different output_dir (used in tests)."""
    return replace(config, output_dir=output_dir)


__all__ = [
    "DEFAULT_CONFIG_PATH",
    "DEFAULT_FILENAME_TEMPLATE",
    "DEFAULT_PORT",
    "ConfigError",
    "ServerConfig",
    "load_or_create_config",
    "save_config",
    "with_output_dir",
]
