from __future__ import annotations

import json
import re
import shutil
import subprocess
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from config_gui import regex_suggest, store
from config_gui.models import ConfigError, normalize_domain
from config_gui.regex_suggest import KNOWN_PATHS, Suggestion, SuggestUnavailable, validate

# One hostile-adjacent path per KNOWN_PATHS entry that has a real path regex: a URL that
# resembles the target section but must NOT match, catching a dropped `(/|$)` terminator.
_HOSTILE_ADJACENT_PATHS: dict[str, str] = {
    "youtube.com": "/watched-later",
    "instagram.com": "/reels-fake",
    "reddit.com": "/rebrand",
    "linkedin.com": "/feeder",
    "netflix.com": "/watchlist",
    "hulu.com": "/watchlist",
    "amazon.com": "/gp/videos",
}

# -- normalization -----------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "youtube.com",
        "https://youtube.com",
        "www.youtube.com",
        "https://www.youtube.com/watch?v=x",
        "YouTube.com",
        "youtube.com:8080",
        "youtube.com/watch",
    ],
)
def test_normalize_domain_reduces_to_bare_domain(raw: str) -> None:
    assert normalize_domain(raw) == "youtube.com"


def test_normalize_domain_rejects_invalid_input() -> None:
    with pytest.raises(ConfigError):
        normalize_domain("not a domain!!")


# -- table -------------------------------------------------------------------


@pytest.mark.parametrize("domain", sorted(KNOWN_PATHS))
def test_known_paths_entries_are_valid(domain: str) -> None:
    path, label = KNOWN_PATHS[domain]
    assert label
    suggestion = Suggestion(host=None, path=path or None, note=label)
    validated = validate(suggestion, advanced=False)
    if validated.path:
        assert validated.path.startswith("^/")


def test_suggest_local_returns_known_entry() -> None:
    suggestion = regex_suggest.suggest_local("https://www.youtube.com/")
    assert suggestion is not None
    assert suggestion.path == r"^/(watch|shorts)(/|$)"


def test_suggest_local_misses_unknown_domain() -> None:
    assert regex_suggest.suggest_local("some-unknown-site.example") is None


@pytest.mark.parametrize("domain", sorted(_HOSTILE_ADJACENT_PATHS))
def test_known_paths_reject_hostile_adjacent_paths(domain: str) -> None:
    path_regex = KNOWN_PATHS[domain][0]
    assert not re.search(path_regex, _HOSTILE_ADJACENT_PATHS[domain])


@pytest.mark.parametrize("domain", sorted(d for d in KNOWN_PATHS if KNOWN_PATHS[d][0]))
def test_match_samples_has_no_false_marks_for_known_paths(domain: str) -> None:
    path, label = KNOWN_PATHS[domain]
    suggestion = Suggestion(host=None, path=path, note=label)
    rows = regex_suggest.match_samples(suggestion, domain)
    mismatches = [row for row in rows if row[1] != row[2]]
    assert mismatches == []


# -- hostile adjacents / match_samples ---------------------------------------


def test_hostile_adjacents_do_not_match_but_subdomain_does() -> None:
    from config_gui.models import host_regex

    pattern = host_regex("youtube.com")
    import re

    assert re.search(pattern, "m.youtube.com")
    assert not re.search(pattern, "notyoutube.com")
    assert not re.search(pattern, "youtube.com.evil.net")


def test_match_samples_flags_hostile_adjacents_as_expected_fail() -> None:
    suggestion = Suggestion(host=None, path=r"^/(watch|shorts)(/|$)", note="videos")
    rows = regex_suggest.match_samples(suggestion, "youtube.com")
    by_url = {url: (matched, expected) for url, matched, expected in rows}
    assert any("notyoutube.com" in url for url in by_url)
    assert any("m.youtube.com" in url for url in by_url)
    for url, (matched, expected) in by_url.items():
        if "notyoutube.com" in url or ".evil.net" in url:
            assert matched is False
            assert expected is False
        if url.startswith("https://m.youtube.com"):
            assert matched is True
            assert expected is True


# -- validate ------------------------------------------------------------------


def test_validate_rejects_unanchored_host() -> None:
    with pytest.raises(ConfigError):
        validate(Suggestion(host="youtube.com", path=None, note=""), advanced=True)


def test_validate_rejects_trailing_dollar_only_host() -> None:
    """`youtube.com$` has a right anchor but no left one — matches `evilyoutube.com`."""
    suggestion = Suggestion(host="youtube.com$", path=None, note="")
    assert re.search(suggestion.host or "", "evilyoutube.com")
    with pytest.raises(ConfigError):
        validate(suggestion, advanced=True)


def test_validate_rejects_wildcard_host() -> None:
    """`.*$` is technically anchored on the right and matches every hostname."""
    with pytest.raises(ConfigError):
        validate(Suggestion(host=".*$", path=None, note=""), advanced=True)


def test_validate_accepts_properly_anchored_host() -> None:
    result = validate(Suggestion(host=r"(^|\.)youtube\.com$", path=None, note=""), advanced=True)
    assert result.host == r"(^|\.)youtube\.com$"


def test_validate_rejects_lookbehind() -> None:
    with pytest.raises(ConfigError):
        validate(Suggestion(host=None, path=r"(?<=/)watch", note=""), advanced=False)
    with pytest.raises(ConfigError):
        validate(Suggestion(host=None, path=r"(?<!/)watch", note=""), advanced=False)


def test_validate_allows_js_named_group() -> None:
    result = validate(
        Suggestion(host=None, path=r"^/(?<section>watch)(/|$)", note=""), advanced=False
    )
    assert result.path == r"^/(?<section>watch)(/|$)"


@pytest.mark.parametrize(
    "pattern",
    [
        r"^/(?i)watch",
        r"^/(?#comment)watch",
        r"^/(?P<section>watch)",
    ],
)
def test_validate_rejects_js_unsupported_extension_syntax(pattern: str) -> None:
    with pytest.raises(ConfigError):
        validate(Suggestion(host=None, path=pattern, note=""), advanced=False)


@pytest.mark.parametrize("pattern", [r"^/(a+)+$", r"^/(.*)*$", r"^/(a*)*$"])
def test_validate_rejects_catastrophic_backtracking_shapes(pattern: str) -> None:
    with pytest.raises(ConfigError):
        validate(Suggestion(host=None, path=pattern, note=""), advanced=False)


def test_validate_rejects_uncompilable_regex() -> None:
    with pytest.raises(ConfigError):
        validate(Suggestion(host=None, path="(unclosed", note=""), advanced=False)


def test_validate_rejects_overlength_pattern() -> None:
    long_path = "^/" + "a" * 300
    with pytest.raises(ConfigError):
        validate(Suggestion(host=None, path=long_path, note=""), advanced=False)


def test_validate_ignores_host_when_not_advanced() -> None:
    result = validate(Suggestion(host="youtube.com", path=None, note=""), advanced=False)
    assert result.host is None


# -- cache ---------------------------------------------------------------------


def test_cache_round_trips() -> None:
    cache = {"key": {"host": None, "path": "^/x", "note": "n"}}
    regex_suggest._write_cache(cache)
    assert regex_suggest._read_cache() == cache


def test_corrupt_cache_is_tolerated() -> None:
    store.suggest_cache_path().write_text("{not json", encoding="utf-8")
    assert regex_suggest._read_cache() == {}


# -- Claude fallback (anthropic SDK, used only when the CLI is unavailable) --------


def test_suggest_via_claude_missing_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _cmd: None)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(SuggestUnavailable):
        regex_suggest.suggest_via_claude("example.com", None, advanced=False)


def test_suggest_via_claude_missing_package_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _cmd: None)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    with patch.dict("sys.modules", {"anthropic": None}):
        with pytest.raises(SuggestUnavailable):
            regex_suggest.suggest_via_claude("example.com", None, advanced=False)


def _mock_client(response_text: str) -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = response_text
    response = MagicMock()
    response.content = [block]
    client = MagicMock()
    client.messages.create.return_value = response
    return client


def test_suggest_via_claude_malformed_json_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _cmd: None)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    fake_module = MagicMock()
    fake_module.Anthropic.return_value = _mock_client("not json")
    with patch.dict("sys.modules", {"anthropic": fake_module}):
        with pytest.raises(SuggestUnavailable):
            regex_suggest.suggest_via_claude("example.com", None, advanced=False)


def test_suggest_via_claude_rejects_unvalidated_response_and_does_not_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A well-typed but semantically bad response (e.g. an unanchored host) must not persist."""
    monkeypatch.setattr(shutil, "which", lambda _cmd: None)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    payload: dict[str, Any] = {"host": "example.com", "path": None, "note": "bad"}
    fake_module = MagicMock()
    fake_module.Anthropic.return_value = _mock_client(json.dumps(payload))
    with patch.dict("sys.modules", {"anthropic": fake_module}):
        with pytest.raises(SuggestUnavailable):
            regex_suggest.suggest_via_claude("example.com", None, advanced=True)

    key = regex_suggest._cache_key("example.com", None, advanced=True)
    assert key not in regex_suggest._read_cache()


def test_suggest_via_claude_sdk_fallback_valid_response_parsed_and_cached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _cmd: None)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    payload: dict[str, Any] = {"host": None, "path": "^/x(/|$)", "note": "test section"}
    fake_module = MagicMock()
    fake_module.Anthropic.return_value = _mock_client(json.dumps(payload))
    with patch.dict("sys.modules", {"anthropic": fake_module}):
        suggestion = regex_suggest.suggest_via_claude("example.com", "x section", advanced=False)

    assert suggestion.path == "^/x(/|$)"
    assert suggestion.note == "test section"
    cached = regex_suggest._read_cache()
    key = regex_suggest._cache_key("example.com", "x section", advanced=False)
    assert key in cached


def test_suggest_via_claude_cached_hit_skips_cli_and_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    key = regex_suggest._cache_key("example.com", None, advanced=False)
    regex_suggest._write_cache({key: {"host": None, "path": "^/cached", "note": "cached"}})

    which = MagicMock()
    monkeypatch.setattr(shutil, "which", which)
    suggestion = regex_suggest.suggest_via_claude("example.com", None, advanced=False)

    assert suggestion.path == "^/cached"
    which.assert_not_called()


# -- Claude Code CLI (primary transport) --------------------------------------


def _mock_cli_run(stdout: str, *, returncode: int = 0) -> MagicMock:
    result = MagicMock()
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = "" if returncode == 0 else "not logged in"
    return result


def test_suggest_via_claude_cli_happy_path_parses_and_caches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {"host": None, "path": "^/x(/|$)", "note": "cli section"}
    envelope = json.dumps({"result": json.dumps(payload)})
    monkeypatch.setattr(shutil, "which", lambda _cmd: "/usr/local/bin/claude")
    mock_run = MagicMock(return_value=_mock_cli_run(envelope))
    monkeypatch.setattr(subprocess, "run", mock_run)

    suggestion = regex_suggest.suggest_via_claude("example.com", "x section", advanced=False)

    assert suggestion.path == "^/x(/|$)"
    assert suggestion.note == "cli section"
    key = regex_suggest._cache_key("example.com", "x section", advanced=False)
    assert key in regex_suggest._read_cache()

    args, kwargs = mock_run.call_args
    assert "--allowed-tools" in args[0]
    assert kwargs.get("shell", False) is False


def test_suggest_via_claude_cli_result_wrapped_in_json_fence_still_parses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {"host": None, "path": "^/y(/|$)", "note": "fenced"}
    fenced_result = f"```json\n{json.dumps(payload)}\n```"
    envelope = json.dumps({"result": fenced_result})
    monkeypatch.setattr(shutil, "which", lambda _cmd: "/usr/local/bin/claude")
    monkeypatch.setattr(subprocess, "run", MagicMock(return_value=_mock_cli_run(envelope)))

    suggestion = regex_suggest.suggest_via_claude("example.com", None, advanced=False)

    assert suggestion.path == "^/y(/|$)"


def test_suggest_via_claude_cli_missing_binary_raises_without_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _cmd: None)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(SuggestUnavailable):
        regex_suggest.suggest_via_claude("example.com", None, advanced=False)


def test_suggest_via_claude_cli_missing_binary_falls_back_to_sdk_when_key_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _cmd: None)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    payload: dict[str, Any] = {"host": None, "path": "^/z(/|$)", "note": "sdk fallback"}
    fake_module = MagicMock()
    fake_module.Anthropic.return_value = _mock_client(json.dumps(payload))
    with patch.dict("sys.modules", {"anthropic": fake_module}):
        suggestion = regex_suggest.suggest_via_claude("example.com", None, advanced=False)

    assert suggestion.path == "^/z(/|$)"
    fake_module.Anthropic.assert_called_once()


def test_suggest_via_claude_cli_nonzero_exit_raises_and_does_not_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _cmd: "/usr/local/bin/claude")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(subprocess, "run", MagicMock(return_value=_mock_cli_run("", returncode=1)))

    with pytest.raises(SuggestUnavailable):
        regex_suggest.suggest_via_claude("example.com", None, advanced=False)

    key = regex_suggest._cache_key("example.com", None, advanced=False)
    assert key not in regex_suggest._read_cache()


def test_suggest_via_claude_cli_present_and_key_set_prefers_cli_over_sdk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CLI wins even when a key is set — the SDK must never be touched."""
    payload = {"host": None, "path": "^/w(/|$)", "note": "cli wins"}
    envelope = json.dumps({"result": json.dumps(payload)})
    monkeypatch.setattr(shutil, "which", lambda _cmd: "/usr/local/bin/claude")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(subprocess, "run", MagicMock(return_value=_mock_cli_run(envelope)))
    fake_module = MagicMock()
    with patch.dict("sys.modules", {"anthropic": fake_module}):
        suggestion = regex_suggest.suggest_via_claude("example.com", None, advanced=False)

    assert suggestion.path == "^/w(/|$)"
    fake_module.Anthropic.assert_not_called()


def test_suggest_via_claude_cli_timeout_raises_and_does_not_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import subprocess as subprocess_module

    monkeypatch.setattr(shutil, "which", lambda _cmd: "/usr/local/bin/claude")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    def _raise_timeout(*_args: object, **_kwargs: object) -> MagicMock:
        raise subprocess_module.TimeoutExpired(cmd="claude", timeout=45.0)

    monkeypatch.setattr(subprocess, "run", _raise_timeout)

    with pytest.raises(SuggestUnavailable):
        regex_suggest.suggest_via_claude("example.com", None, advanced=False)

    key = regex_suggest._cache_key("example.com", None, advanced=False)
    assert key not in regex_suggest._read_cache()


def test_suggest_via_claude_cli_oserror_raises_suggest_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A binary that `which` found but that can't be executed must not escape as an OSError."""
    monkeypatch.setattr(shutil, "which", lambda _cmd: "/usr/local/bin/claude")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    def _raise_oserror(*_args: object, **_kwargs: object) -> MagicMock:
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(subprocess, "run", _raise_oserror)

    with pytest.raises(SuggestUnavailable):
        regex_suggest.suggest_via_claude("example.com", None, advanced=False)

    key = regex_suggest._cache_key("example.com", None, advanced=False)
    assert key not in regex_suggest._read_cache()


def test_suggest_via_claude_cache_hit_never_calls_subprocess(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key = regex_suggest._cache_key("example.com", None, advanced=False)
    regex_suggest._write_cache({key: {"host": None, "path": "^/cached", "note": "cached"}})

    monkeypatch.setattr(shutil, "which", lambda _cmd: "/usr/local/bin/claude")
    run = MagicMock()
    monkeypatch.setattr(subprocess, "run", run)

    suggestion = regex_suggest.suggest_via_claude("example.com", None, advanced=False)

    assert suggestion.path == "^/cached"
    run.assert_not_called()


def test_suggest_via_claude_cli_invalid_envelope_writes_nothing_to_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _cmd: "/usr/local/bin/claude")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(subprocess, "run", MagicMock(return_value=_mock_cli_run("not json")))

    with pytest.raises(SuggestUnavailable):
        regex_suggest.suggest_via_claude("example.com", None, advanced=False)

    assert regex_suggest._read_cache() == {}


# -- _extract_json --------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('{"a": 1}', '{"a": 1}'),
        ('```json\n{"a": 1}\n```', '{"a": 1}'),
        ('```\n{"a": 1}\n```', '{"a": 1}'),
        ('Sure, here it is:\n```json\n{"a": 1}\n```\nHope that helps!', '{"a": 1}'),
        ("just some prose, no JSON here", "just some prose, no JSON here"),
    ],
)
def test_extract_json(text: str, expected: str) -> None:
    assert regex_suggest._extract_json(text) == expected


# -- _claude_cli_text envelope edge cases ---------------------------------------


@pytest.mark.parametrize(
    "stdout",
    [
        "not json at all",
        "[1, 2, 3]",
        json.dumps({"other_key": "value"}),
        json.dumps({"result": None}),
        json.dumps({"result": {"nested": True}}),
    ],
)
def test_claude_cli_text_rejects_bad_envelopes(
    monkeypatch: pytest.MonkeyPatch, stdout: str
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _cmd: "/usr/local/bin/claude")
    monkeypatch.setattr(subprocess, "run", MagicMock(return_value=_mock_cli_run(stdout)))

    with pytest.raises(SuggestUnavailable):
        regex_suggest._claude_cli_text("prompt")
