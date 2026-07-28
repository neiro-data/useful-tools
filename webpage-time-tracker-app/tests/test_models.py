from __future__ import annotations

import re

import pytest

from config_gui.models import Config, ConfigError, Site, domain_from_host_regex, host_regex


@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        ("youtube.com", r"(^|\.)youtube\.com$"),
        ("  YouTube.com ", r"(^|\.)youtube\.com$"),
        ("https://www.youtube.com/feed", r"(^|\.)youtube\.com$"),
    ],
)
def test_host_regex_normalises_what_the_user_types(typed: str, expected: str) -> None:
    assert host_regex(typed) == expected


def test_host_regex_matches_the_domain_and_its_subdomains() -> None:
    pattern = re.compile(host_regex("youtube.com"))
    assert pattern.search("youtube.com")
    assert pattern.search("m.youtube.com")
    assert not pattern.search("notyoutube.com")
    assert not pattern.search("youtube.com.evil.net")


def test_domain_round_trips() -> None:
    assert domain_from_host_regex(host_regex("instagram.com")) == "instagram.com"


def test_domain_is_empty_for_hand_written_patterns() -> None:
    assert Site(name="X", host=r"(^|\.)(x|twitter)\.com$", limit_minutes=30).domain == ""


@pytest.mark.parametrize("typed", ["", "   ", "not a domain", "http://"])
def test_host_regex_rejects_non_domains(typed: str) -> None:
    with pytest.raises(ConfigError):
        host_regex(typed)


@pytest.mark.parametrize(
    "site",
    [
        Site(name="", host=r"a$", limit_minutes=5),
        Site(name="Bad regex", host=r"(unclosed", limit_minutes=5),
        Site(name="Bad path", host=r"a$", limit_minutes=5, path=r"["),
        Site(name="Zero", host=r"a$", limit_minutes=0),
        Site(name="Too much", host=r"a$", limit_minutes=1441),
    ],
)
def test_site_validation_rejects(site: Site) -> None:
    with pytest.raises(ConfigError):
        site.validated()


def test_config_round_trips_through_json_shape() -> None:
    original = Config()
    restored = Config.from_dict(original.to_dict())
    assert restored == original
    assert original.to_dict()["sites"][0]["path"] == "^/shorts(/|$)"


def test_config_rejects_duplicate_site_names() -> None:
    config = Config(sites=[Site.from_domain("A", "a.com", 5), Site.from_domain("A", "b.com", 5)])
    with pytest.raises(ConfigError):
        config.validated()


@pytest.mark.parametrize(
    "data",
    [
        {"sites": "nope"},
        {"sites": [{"name": "A", "host": "(", "limitMinutes": 5}]},
        {"sites": [{"name": "A", "limitMinutes": 5}]},
        {"sites": [], "dayStartHour": 99},
    ],
)
def test_config_from_dict_rejects_bad_input(data: dict[str, object]) -> None:
    with pytest.raises(ConfigError):
        Config.from_dict(data)
