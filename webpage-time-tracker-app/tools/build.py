"""Deterministic, dependency-free build for the two userscript dist files.

Each dist file is a straight concatenation of a header (metadata block), the
platform-agnostic core, and a platform adapter. No templating, no bundler —
just bytes in, bytes out, so ``--check`` can assert dist/ matches src/.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = APP_ROOT / "src"
DIST_DIR = APP_ROOT / "dist"

# (header, core, adapter) -> dist filename, in build order.
TARGETS: tuple[tuple[str, str, str, str], ...] = (
    ("header-chrome.js", "core.js", "adapter-gm.js", "webpage-time-tracker.user.js"),
    ("header-safari.js", "core.js", "adapter-safari.js", "webpage-time-tracker.safari.user.js"),
)


def _read(name: str) -> str:
    return (SRC_DIR / name).read_text(encoding="utf-8")


def render(header: str, core: str, adapter: str) -> str:
    """Concatenate the three source parts into one dist file's contents."""
    parts = [_read(header).rstrip("\n"), _read(core).rstrip("\n"), _read(adapter).rstrip("\n")]
    return "\n\n".join(parts) + "\n"


def build(check: bool) -> bool:
    """Build (or, with check=True, verify) every dist target.

    Returns True if dist/ is up to date with src/ for every target.
    """
    up_to_date = True
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    for header, core, adapter, dist_name in TARGETS:
        content = render(header, core, adapter)
        dist_path = DIST_DIR / dist_name
        try:
            display_path = dist_path.relative_to(APP_ROOT)
        except ValueError:
            # Cosmetic only — a relocated DIST_DIR must never fail the build.
            display_path = dist_path

        if check:
            current = dist_path.read_text(encoding="utf-8") if dist_path.exists() else None
            if current != content:
                up_to_date = False
                print(f"stale: {display_path}", file=sys.stderr)
            continue

        dist_path.write_text(content, encoding="utf-8")
        print(f"wrote {display_path}")

    return up_to_date


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify dist/ matches src/ without writing; exit non-zero if stale",
    )
    args = parser.parse_args()

    up_to_date = build(check=args.check)
    if args.check and not up_to_date:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
