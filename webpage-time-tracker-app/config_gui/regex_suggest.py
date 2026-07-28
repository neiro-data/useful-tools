"""Suggests host/path regexes for the Site dialog — a lookup table first, Claude on a miss.

Every suggestion, from either source, is validated against the same JS-`RegExp`
compatibility rules `models.py` already enforces on saved sites before it is
ever shown to the user.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess  # noqa: S404 - `claude` CLI invoked with a fixed argv, never shell=True
from dataclasses import dataclass

from config_gui import store
from config_gui.models import ConfigError, normalize_domain

_CLAUDE_MODEL = "claude-haiku-4-5"
_TIMEOUT_SECONDS = 15.0
_CLI_TIMEOUT_SECONDS = 45.0
_MAX_PATTERN_LENGTH = 200
_MAX_HINT_LENGTH = 200
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)

# A group with a quantifier inside, itself quantified — the classic catastrophic-backtracking
# shape (`(a+)+`, `(.*)*` ...). Only a heuristic, but cheap and catches the free-text-hint risk.
_CATASTROPHIC_BACKTRACK_RE = re.compile(r"\([^()]*[+*][^()]*\)[+*]")

# Extension groups JS `RegExp` doesn't support: inline flags `(?i)`, comments `(?#...)`, and
# Python-style named groups `(?P<name>...)`. `(?:...)`, `(?=...)`, `(?!...)`, and the JS named
# group `(?<name>...)` are all fine and must not be rejected.
_LOOKBEHIND_RE = re.compile(r"\(\?<[=!]")
_UNSUPPORTED_EXT_RE = re.compile(r"\(\?(?!:|=|!|<(?![=!]))")
_JS_NAMED_GROUP_RE = re.compile(r"\(\?<(?![=!])(\w+)>")


class SuggestUnavailable(ConfigError):
    """Claude suggestion could not be produced — missing CLI/key, package, or a failed call."""


@dataclass(frozen=True)
class Suggestion:
    host: str | None
    path: str | None
    note: str


# domain -> (path_regex, human label). "" means the whole site is the time sink.
KNOWN_PATHS: dict[str, tuple[str, str]] = {
    "youtube.com": (r"^/(watch|shorts)(/|$)", "videos and shorts"),
    "instagram.com": (r"^/reels?(/|$)", "reels"),
    "reddit.com": (r"^/r/", "any subreddit"),
    "tiktok.com": ("", "the whole site is short-form video"),
    "x.com": ("", "the whole site is the feed"),
    "twitter.com": ("", "the whole site is the feed"),
    "facebook.com": ("", "the whole site is the feed"),
    "news.ycombinator.com": ("", "the whole site is the feed"),
    "twitch.tv": ("", "the whole site is livestreams"),
    "linkedin.com": (r"^/feed(/|$)", "the feed"),
    "pinterest.com": ("", "the whole site is the feed"),
    "tumblr.com": ("", "the whole site is the feed"),
    "9gag.com": ("", "the whole site is the feed"),
    "imgur.com": ("", "the whole site is the feed"),
    "quora.com": ("", "the whole site is the feed"),
    "medium.com": ("", "the whole site is articles"),
    "substack.com": ("", "the whole site is articles"),
    "netflix.com": (r"^/watch(/|$)", "video playback"),
    "hulu.com": (r"^/watch(/|$)", "video playback"),
    "primevideo.com": ("", "the whole site is video playback"),
    "amazon.com": (r"^/gp/video(/|$)", "Prime Video section"),
    "disneyplus.com": ("", "the whole site is video playback"),
    "spotify.com": ("", "the whole site is playback"),
    "soundcloud.com": ("", "the whole site is playback"),
    "discord.com": ("", "the whole site is chat"),
    "telegram.org": ("", "the whole site is chat"),
    "web.telegram.org": ("", "the whole site is chat"),
    "whatsapp.com": ("", "the whole site is chat"),
    "web.whatsapp.com": ("", "the whole site is chat"),
    "bsky.app": ("", "the whole site is the feed"),
    "mastodon.social": ("", "the whole site is the feed"),
    "threads.net": ("", "the whole site is the feed"),
    "snapchat.com": ("", "the whole site is the feed"),
    "vk.com": ("", "the whole site is the feed"),
    "weibo.com": ("", "the whole site is the feed"),
}


def suggest_local(domain: str) -> Suggestion | None:
    """A table hit for `domain`, or None to fall through to Claude."""
    cleaned = normalize_domain(domain)
    entry = KNOWN_PATHS.get(cleaned)
    if entry is None:
        return None
    path, label = entry
    return Suggestion(host=None, path=path or None, note=f"Known section: {label}.")


def validate(suggestion: Suggestion, *, advanced: bool) -> Suggestion:
    """Enforce the JS-`RegExp` compatibility rules before a suggestion is ever shown."""
    host = suggestion.host if advanced else None
    path = suggestion.path

    for label, pattern in (("host", host), ("path", path)):
        if not pattern:
            continue
        if len(pattern) > _MAX_PATTERN_LENGTH:
            raise ConfigError(f"{label} suggestion is too long")
        if _LOOKBEHIND_RE.search(pattern):
            raise ConfigError(f"{label} suggestion uses lookbehind, unsupported by the userscript")
        if _UNSUPPORTED_EXT_RE.search(pattern):
            raise ConfigError(
                f"{label} suggestion uses a regex feature JS `RegExp` does not support "
                "(inline flags, comments, or Python-style named groups)"
            )
        if _CATASTROPHIC_BACKTRACK_RE.search(pattern):
            raise ConfigError(f"{label} suggestion risks catastrophic backtracking")
        try:
            # Python's `re` only understands `(?P<name>...)`, not JS's `(?<name>...)` — translate
            # for the compile check alone; the original JS-flavoured source is what gets stored.
            re.compile(_JS_NAMED_GROUP_RE.sub(r"(?P<\1>", pattern))
        except re.error as err:
            raise ConfigError(f"{label} suggestion is not a valid regex: {err}") from err

    if host:
        if not host.endswith("$"):
            raise ConfigError("host suggestion must be anchored (end with `$`)")
        if not (host.startswith("^") or host.startswith(r"(^|\.)")):
            raise ConfigError(
                "host suggestion must anchor its left edge with `^` or `(^|\\.)` — a bare "
                "trailing `$` still lets it match as a substring of an unrelated hostname"
            )

    return Suggestion(host=host, path=path, note=suggestion.note)


def match_samples(suggestion: Suggestion, domain: str) -> list[tuple[str, bool, bool]]:
    """Preview rows of `(sample_url, matched, expected)` for the GUI's pass/fail table."""
    cleaned = normalize_domain(domain)
    host_pattern = suggestion.host or rf"(^|\.){re.escape(cleaned)}$"

    hosts: list[tuple[str, bool]] = [
        (cleaned, True),
        (f"m.{cleaned}", True),
        (f"not{cleaned}", False),
        (f"{cleaned}.evil.net", False),
    ]
    rows: list[tuple[str, bool, bool]] = []
    for host, expected in hosts:
        matched = re.search(host_pattern, host) is not None
        rows.append((f"https://{host}/", matched, expected))

    if suggestion.path:
        on_sample = _sample_path(suggestion.path, matching=True)
        off_sample = _sample_path(suggestion.path, matching=False)
        rows.append(
            (
                f"https://{cleaned}{on_sample}",
                re.search(suggestion.path, on_sample) is not None,
                True,
            )
        )
        rows.append(
            (
                f"https://{cleaned}{off_sample}",
                re.search(suggestion.path, off_sample) is not None,
                False,
            )
        )
    return rows


def _sample_path(pattern: str, *, matching: bool) -> str:
    """A concrete path that should (or should not) satisfy a `^/section(/|$)`-style pattern."""
    if matching:
        return _resolve_literal(pattern) or "/section/"
    return "/unrelated-page"


def _resolve_literal(fragment: str) -> str:
    """Walk a simple `^/section(a|b)?(/|$)`-style fragment and build one matching literal.

    Handles what `KNOWN_PATHS`/Claude actually produce: anchors, escapes, `(a|b)` alternation
    (first branch), and a trailing `?`/`*` on the previous atom — enough to make the preview's
    "on-path" sample actually satisfy the pattern instead of a token-stripped guess.
    """
    out: list[str] = []
    i, n = 0, len(fragment)
    while i < n:
        char = fragment[i]
        if char in "^$":
            i += 1
            continue
        if char == "\\" and i + 1 < n:
            out.append(fragment[i + 1])
            i += 2
        elif char == "(":
            depth = 1
            j = i + 1
            while j < n and depth:
                if fragment[j] == "(":
                    depth += 1
                elif fragment[j] == ")":
                    depth -= 1
                j += 1
            inner = fragment[i + 1 : j - 1]
            out.append(_resolve_literal(inner.split("|")[0]))
            i = j
            if i < n and fragment[i] in "?*":
                i += 1
        else:
            out.append(char)
            i += 1
            if i < n and fragment[i] == "?":
                i += 1
    return "".join(out)


def _cache_key(domain: str, hint: str | None, *, advanced: bool) -> str:
    return json.dumps([normalize_domain(domain), hint or "", advanced])


def _read_cache() -> dict[str, dict[str, str | None]]:
    path = store.suggest_cache_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_cache(cache: dict[str, dict[str, str | None]]) -> None:
    try:
        store.write_atomic(store.suggest_cache_path(), json.dumps(cache))
    except OSError:
        pass


def _extract_json(text: str) -> str:
    """Strip a ```/```json fence and surrounding prose, if any, from Claude's raw text."""
    match = _JSON_FENCE_RE.search(text)
    return match.group(1).strip() if match else text.strip()


def _claude_cli_text(prompt: str) -> str:
    """Run the Claude Code CLI non-interactively and return its `result` text."""
    claude = shutil.which("claude")
    if claude is None:
        raise SuggestUnavailable("Claude Code CLI (`claude`) not found on PATH")

    # `--allowed-tools ""` is defense-in-depth for a prompt built partly from a free-text hint,
    # not a sandbox — the CLI still inherits this process's env, cwd, and permissions.
    try:
        proc = subprocess.run(  # noqa: S603 - fixed argv, no shell, no user-controlled binary
            [
                claude,
                "-p",
                prompt,
                "--output-format",
                "json",
                "--model",
                _CLAUDE_MODEL,
                "--allowed-tools",
                "",
            ],
            capture_output=True,
            text=True,
            timeout=_CLI_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as err:
        raise SuggestUnavailable("Claude Code CLI timed out") from err
    except OSError as err:
        # `which` only proved the path existed a moment ago — it can still be non-executable,
        # or vanish. Nothing but `SuggestUnavailable` may escape: the worker thread's only
        # handler is `except ConfigError`, and anything else kills it with the button stuck.
        raise SuggestUnavailable(f"Claude Code CLI could not be run: {err}") from err

    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        raise SuggestUnavailable(
            f"Claude Code CLI failed: {stderr}" if stderr else "Claude Code CLI failed"
        )

    try:
        envelope = json.loads(proc.stdout)
    except json.JSONDecodeError as err:
        raise SuggestUnavailable("Claude Code CLI returned invalid JSON") from err

    result = envelope.get("result") if isinstance(envelope, dict) else None
    if not isinstance(result, str):
        raise SuggestUnavailable("Claude Code CLI returned an unexpected response")
    return result


def _claude_sdk_text(prompt: str) -> str:
    """Fall back to the `anthropic` SDK, used only when the CLI is unavailable."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise SuggestUnavailable("ANTHROPIC_API_KEY is not set")

    try:
        import anthropic
    except ImportError as err:
        raise SuggestUnavailable("the anthropic package is not installed") from err

    try:
        client = anthropic.Anthropic(api_key=api_key, timeout=_TIMEOUT_SECONDS)
        response = client.messages.create(
            model=_CLAUDE_MODEL,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            getattr(block, "text", "")
            for block in response.content
            if getattr(block, "type", None) == "text"
        )
    except Exception as err:  # any SDK/network failure must surface as SuggestUnavailable
        raise SuggestUnavailable(f"Claude suggestion failed: {err}") from err


def suggest_via_claude(domain: str, hint: str | None, *, advanced: bool) -> Suggestion:
    """Ask Claude for a suggestion, using a disk cache; only raises `SuggestUnavailable`.

    Tries the Claude Code CLI first; falls back to the `anthropic` SDK only if the CLI is
    unavailable and `ANTHROPIC_API_KEY` is set. Only a `validate()`-passing suggestion is ever
    cached — an unvalidated response would otherwise be replayed, and fail identically, on every
    future click.
    """
    cleaned = normalize_domain(domain)
    hint = hint[:_MAX_HINT_LENGTH] if hint else hint
    key = _cache_key(cleaned, hint, advanced=advanced)
    cache = _read_cache()
    cached = cache.get(key)
    if cached is not None:
        return Suggestion(
            host=cached.get("host"), path=cached.get("path"), note=cached.get("note") or ""
        )

    prompt = _build_prompt(cleaned, hint, advanced=advanced)
    try:
        text = _claude_cli_text(prompt)
    except SuggestUnavailable:
        if os.getenv("ANTHROPIC_API_KEY"):
            text = _claude_sdk_text(prompt)
        else:
            raise

    try:
        payload = json.loads(_extract_json(text))
    except json.JSONDecodeError as err:
        raise SuggestUnavailable(f"Claude suggestion failed: {err}") from err

    if not isinstance(payload, dict) or not {"host", "path", "note"} <= payload.keys():
        raise SuggestUnavailable("Claude returned an unexpected response")
    host, path, note = payload["host"], payload["path"], payload["note"]
    if not (host is None or isinstance(host, str)):
        raise SuggestUnavailable("Claude returned a non-string host")
    if not (path is None or isinstance(path, str)):
        raise SuggestUnavailable("Claude returned a non-string path")
    if not isinstance(note, str):
        raise SuggestUnavailable("Claude returned a non-string note")

    try:
        suggestion = validate(Suggestion(host=host, path=path, note=note), advanced=advanced)
    except ConfigError as err:
        raise SuggestUnavailable(f"Claude suggestion failed validation: {err}") from err

    cache[key] = {"host": suggestion.host, "path": suggestion.path, "note": suggestion.note}
    _write_cache(cache)
    return suggestion


def _build_prompt(domain: str, hint: str | None, *, advanced: bool) -> str:
    hint_line = f'The user only wants to match: "{hint}".' if hint else "No further hint given."
    host_ask = (
        "Also propose a `host` regex anchored to end with `$`, matching the domain and its "
        "subdomains."
        if advanced
        else "Set `host` to null — the caller already derives it from the plain domain."
    )
    return (
        f"Domain: {domain}\n{hint_line}\n{host_ask}\n\n"
        "Propose a `path` regex (JavaScript RegExp source, matched against a URL path) for the "
        "section of this site to track, or null if the whole site should count and no path "
        "filter is needed.\n"
        "Rules: JavaScript RegExp syntax only; no lookbehind; no named groups; a `path` must "
        "start with `^/`; prefer a `(/|$)` terminator over a bare prefix; a `host` (if any) must "
        "end with `$`.\n"
        'Respond with STRICT JSON only, no prose: {"host": string|null, "path": string|null, '
        '"note": string}'
    )
