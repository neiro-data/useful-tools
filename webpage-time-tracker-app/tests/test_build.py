from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tools import build

APP_ROOT = Path(__file__).resolve().parent.parent
SRC_NAMES = (
    "header-chrome.js",
    "header-safari.js",
    "core.js",
    "adapter-gm.js",
    "adapter-safari.js",
)


def _copy_src(tmp_path: Path) -> Path:
    src_copy = tmp_path / "src"
    src_copy.mkdir()
    for name in SRC_NAMES:
        (src_copy / name).write_text((build.SRC_DIR / name).read_text(encoding="utf-8"))
    return src_copy


def test_build_is_deterministic() -> None:
    """Same source input renders byte-identical output across two runs."""
    first = build.render("header-chrome.js", "core.js", "adapter-gm.js")
    second = build.render("header-chrome.js", "core.js", "adapter-gm.js")
    assert first == second


def test_check_passes_when_dist_is_current() -> None:
    assert build.build(check=True) is True


def test_check_fails_when_dist_is_stale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _copy_src(tmp_path)
    dist_copy = tmp_path / "dist"
    monkeypatch.setattr(build, "APP_ROOT", tmp_path)
    monkeypatch.setattr(build, "SRC_DIR", tmp_path / "src")
    monkeypatch.setattr(build, "DIST_DIR", dist_copy)
    assert build.build(check=False) is True

    stale = dist_copy / "webpage-time-tracker.user.js"
    stale.write_text(stale.read_text(encoding="utf-8") + "\n// stale marker\n", encoding="utf-8")

    assert build.build(check=True) is False


def test_check_fails_when_dist_file_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _copy_src(tmp_path)
    dist_copy = tmp_path / "dist"
    monkeypatch.setattr(build, "APP_ROOT", tmp_path)
    monkeypatch.setattr(build, "SRC_DIR", tmp_path / "src")
    monkeypatch.setattr(build, "DIST_DIR", dist_copy)
    assert build.build(check=False) is True

    (dist_copy / "webpage-time-tracker.safari.user.js").unlink()

    assert build.build(check=True) is False


def test_build_writes_the_expected_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(build, "APP_ROOT", tmp_path)
    monkeypatch.setattr(build, "DIST_DIR", tmp_path / "dist")
    expected_chrome = build.render("header-chrome.js", "core.js", "adapter-gm.js")
    expected_safari = build.render("header-safari.js", "core.js", "adapter-safari.js")

    assert build.build(check=False) is True

    chrome = (tmp_path / "dist" / "webpage-time-tracker.user.js").read_text(encoding="utf-8")
    safari = (tmp_path / "dist" / "webpage-time-tracker.safari.user.js").read_text(encoding="utf-8")
    assert chrome == expected_chrome
    assert safari == expected_safari


def test_render_raises_when_a_source_file_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(build, "SRC_DIR", build.SRC_DIR.parent / "does-not-exist")
    with pytest.raises(FileNotFoundError):
        build.render("header-chrome.js", "core.js", "adapter-gm.js")


def test_config_poll_backs_off_and_never_stops_permanently() -> None:
    """Regression for the config-poll defect: on failure the poll must back
    off (not clearInterval permanently), and success must reset the delay."""
    core = (build.SRC_DIR / "core.js").read_text(encoding="utf-8")

    # No permanent-stop path: clearInterval on the config poll handle is gone.
    assert "clearInterval(configPollHandle)" not in core

    # Self-rescheduling backoff, capped, resetting to the base interval.
    assert "MAX_CONFIG_POLL_MS" in core
    assert "reschedulePoll" in core
    assert "configFailures = 0" in core  # reset on success
    assert "2 ** configFailures" in core  # exponential growth on failure


def test_untracked_pages_warm_the_cache_but_schedule_no_poll() -> None:
    """Regression: @match is *://*/*, so the script runs on every page on the web.

    A page whose hostname matches no rule must fetch the config once and then
    schedule nothing — otherwise every open tab holds a timer polling the
    loopback server for the life of the tab. The ordering below is the whole
    guarantee: the eager fetch happens before the early-out, the flag that
    unlocks scheduling is set after it.
    """
    core = (build.SRC_DIR / "core.js").read_text(encoding="utf-8")

    eager_fetch = core.index("await refreshConfig()")
    early_out = core.index("if (!CONFIG.rules.some((rule) => rule.host.test(location.hostname)))")
    unlock = core.index("pollingStarted = true")

    assert eager_fetch < early_out, "the cache-warming fetch must run before the early-out"
    assert early_out < unlock, "scheduling must not be unlocked until the early-out has passed"

    # The gate itself: reschedulePoll is inert until the flag is set.
    assert "if (!pollingStarted) return;" in core


def test_cli_check_exits_zero_when_current() -> None:
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(APP_ROOT / "tools" / "build.py"), "--check"],
        cwd=APP_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_cli_check_exits_nonzero_when_stale(tmp_path: Path) -> None:
    """Run the real CLI against a scratch copy of the repo, never the real dist/."""
    root_copy = tmp_path / "app"
    (root_copy / "src").mkdir(parents=True)
    (root_copy / "tools").mkdir()
    (root_copy / "dist").mkdir()
    for name in SRC_NAMES:
        (root_copy / "src" / name).write_text(
            (build.SRC_DIR / name).read_text(encoding="utf-8"), encoding="utf-8"
        )
    (root_copy / "tools" / "build.py").write_text(
        (APP_ROOT / "tools" / "build.py").read_text(encoding="utf-8"), encoding="utf-8"
    )

    build_script = root_copy / "tools" / "build.py"
    subprocess.run(  # noqa: S603
        [sys.executable, str(build_script)],
        cwd=root_copy,
        capture_output=True,
        text=True,
        check=True,
    )
    stale = root_copy / "dist" / "webpage-time-tracker.user.js"
    stale.write_text(stale.read_text(encoding="utf-8") + "\n// stale marker\n", encoding="utf-8")

    result = subprocess.run(  # noqa: S603
        [sys.executable, str(build_script), "--check"],
        cwd=root_copy,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "stale" in result.stderr


def test_safari_header_injects_into_content() -> None:
    """Regression: the Safari build shipped `@inject-into page`, and
    Userscripts.app exposes the GM APIs only to scripts injected into
    `content`. In the page world every GM call threw, the adapter swallowed
    it, and the script ran on its baked-in DEFAULTS: nothing persisted and the
    settings server was never contacted, while the badge looked healthy.
    """
    header = (build.SRC_DIR / "header-safari.js").read_text(encoding="utf-8")

    assert "@inject-into  content" in header
    assert "@inject-into  page" not in header
    # The grants the adapter depends on must still be declared.
    for grant in ("GM.getValue", "GM.setValue", "GM.xmlHttpRequest"):
        assert f"@grant        {grant}" in header


def test_safari_adapter_warns_when_gm_is_missing() -> None:
    """The failure above was silent for a whole release. A missing GM API is
    unrecoverable, so it must be reported — once, not once per storage call."""
    adapter = (build.SRC_DIR / "adapter-safari.js").read_text(encoding="utf-8")

    assert "console.warn" in adapter
    assert "warnedNoGM" in adapter  # the once-only latch
    # Every entry point into the GM API guards, not just the fetch path.
    assert adapter.count("warnOnce()") >= 3
