"""Config data model, validation, and the plain-domain → regex translation.

`host` and `path` travel to the userscript as regex *source strings* and are
compiled there with `new RegExp(...)`. They are validated here with
`re.compile` — the two flavours differ in corners this app never generates
(named groups, lookbehind), so a pattern this module accepts is one the script
can compile.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

CONFIG_VERSION = 1

MAX_LIMIT_MINUTES = 24 * 60


class ConfigError(ValueError):
    """A config value the userscript could not act on."""


def normalize_domain(value: str) -> str:
    """Strip scheme/path/port/`www.` and lowercase — shared by `host_regex` and suggestions."""
    cleaned = value.strip().lower()
    cleaned = re.sub(r"^[a-z]+://", "", cleaned)
    cleaned = cleaned.split("/")[0]
    cleaned = cleaned.split(":")[0]
    cleaned = cleaned.removeprefix("www.").strip(".")
    if not cleaned or not re.fullmatch(r"[a-z0-9.-]+", cleaned):
        raise ConfigError(f"not a domain: {value!r}")
    return cleaned


def host_regex(domain: str) -> str:
    """`youtube.com` → `(^|\\.)youtube\\.com$` — the domain and its subdomains."""
    cleaned = normalize_domain(domain)
    return rf"(^|\.){re.escape(cleaned)}$"


def domain_from_host_regex(source: str) -> str:
    """Inverse of `host_regex` for patterns it produced; "" for hand-written ones."""
    match = re.fullmatch(r"\(\^\|\\\.\)(.+)\$", source)
    if not match:
        return ""
    inner = match.group(1)
    plain = re.sub(r"\\(.)", r"\1", inner)
    return plain if re.fullmatch(r"[a-z0-9.-]+", plain) else ""


def _valid_regex(source: str, label: str) -> str:
    try:
        re.compile(source)
    except re.error as err:
        raise ConfigError(f"{label} is not a valid regex: {err}") from err
    return source


@dataclass
class Site:
    name: str
    host: str
    limit_minutes: int
    path: str | None = None

    @classmethod
    def from_domain(
        cls, name: str, domain: str, limit_minutes: int, path: str | None = None
    ) -> Site:
        return cls(
            name=name, host=host_regex(domain), limit_minutes=limit_minutes, path=path or None
        ).validated()

    @property
    def domain(self) -> str:
        """Display domain — empty when `host` is a hand-written pattern."""
        return domain_from_host_regex(self.host)

    def validated(self) -> Site:
        if not self.name.strip():
            raise ConfigError("site name is required")
        _valid_regex(self.host, "host")
        if self.path:
            _valid_regex(self.path, "path")
        if not isinstance(self.limit_minutes, int) or isinstance(self.limit_minutes, bool):
            raise ConfigError("limit must be a whole number of minutes")
        if not 1 <= self.limit_minutes <= MAX_LIMIT_MINUTES:
            raise ConfigError(f"limit must be between 1 and {MAX_LIMIT_MINUTES} minutes")
        return self

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "name": self.name.strip(),
            "host": self.host,
            "limitMinutes": self.limit_minutes,
        }
        if self.path:
            data["path"] = self.path
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Site:
        try:
            return cls(
                name=str(data["name"]),
                host=str(data["host"]),
                limit_minutes=int(data["limitMinutes"]),
                path=str(data["path"]) if data.get("path") else None,
            ).validated()
        except (KeyError, TypeError, ValueError) as err:
            if isinstance(err, ConfigError):
                raise
            raise ConfigError(f"malformed site entry: {err}") from err


def _default_sites() -> list[Site]:
    return [
        Site.from_domain("YouTube Shorts", "youtube.com", 15, r"^/shorts(/|$)"),
        Site.from_domain("Instagram Reels", "instagram.com", 15, r"^/reels?(/|$)"),
        Site(name="X", host=r"(^|\.)(x|twitter)\.com$", limit_minutes=30),
    ]


@dataclass
class Config:
    day_start_hour: int = 4
    idle_seconds: int = 60
    snooze_minutes: int = 5
    history_days: int = 14
    sites: list[Site] = field(default_factory=_default_sites)

    def validated(self) -> Config:
        if not 0 <= self.day_start_hour <= 23:
            raise ConfigError("dayStartHour must be 0–23")
        if self.idle_seconds < 5:
            raise ConfigError("idleSeconds must be at least 5")
        if self.snooze_minutes < 1:
            raise ConfigError("snoozeMinutes must be at least 1")
        if not 1 <= self.history_days <= 365:
            raise ConfigError("historyDays must be 1–365")
        names = [site.validated().name.strip() for site in self.sites]
        if len(set(names)) != len(names):
            # Names key the stored counters, so duplicates would share a bucket.
            raise ConfigError("site names must be unique")
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": CONFIG_VERSION,
            "dayStartHour": self.day_start_hour,
            "idleSeconds": self.idle_seconds,
            "snoozeMinutes": self.snooze_minutes,
            "historyDays": self.history_days,
            "sites": [site.to_dict() for site in self.sites],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Config:
        if not isinstance(data, dict):
            raise ConfigError("config must be an object")
        raw_sites = data.get("sites")
        if not isinstance(raw_sites, list):
            raise ConfigError("config.sites must be a list")
        defaults = cls()
        try:
            return cls(
                day_start_hour=int(data.get("dayStartHour", defaults.day_start_hour)),
                idle_seconds=int(data.get("idleSeconds", defaults.idle_seconds)),
                snooze_minutes=int(data.get("snoozeMinutes", defaults.snooze_minutes)),
                history_days=int(data.get("historyDays", defaults.history_days)),
                sites=[Site.from_dict(entry) for entry in raw_sites],
            ).validated()
        except (TypeError, ValueError) as err:
            if isinstance(err, ConfigError):
                raise
            raise ConfigError(f"malformed config: {err}") from err
