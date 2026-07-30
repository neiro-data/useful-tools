"""A stale dist/ must never make it into a commit.

Regenerates both dist files from src/ into a tmpdir and asserts byte-equality
with the committed files, so a src/ edit without a matching `uv run tools/build.py`
run fails CI rather than shipping a stale userscript.
"""

from __future__ import annotations

from pathlib import Path

from tools import build

APP_ROOT = Path(__file__).resolve().parent.parent

DIST_TARGETS = (
    "webpage-time-tracker.user.js",
    "webpage-time-tracker.safari.user.js",
)


def test_dist_matches_src(tmp_path: Path) -> None:
    generated = {
        "webpage-time-tracker.user.js": build.render(
            "header-chrome.js", "core.js", "adapter-gm.js"
        ),
        "webpage-time-tracker.safari.user.js": build.render(
            "header-safari.js", "core.js", "adapter-safari.js"
        ),
    }

    for name, content in generated.items():
        out = tmp_path / name
        out.write_text(content, encoding="utf-8")

        committed = (build.DIST_DIR / name).read_bytes()
        assert out.read_bytes() == committed, (
            f"{name} is stale — run `uv run python tools/build.py` and commit the result"
        )
