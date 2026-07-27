"""Tests for ``app/report_theme.py``: literal design-token constants and helpers used by the
report exports (HTML/PDF/Markdown)."""

import re
from pathlib import Path

import pytest

from app.report_theme import (
    CAT_PALETTE,
    FALLBACK_CAT,
    hex_to_rgb,
    resolve_category_color,
    tag_gray,
)

TOKENS_CSS_PATH = Path(__file__).resolve().parent.parent / "design" / "tokens.css"

_SEMANTIC_TOKEN_CSS_VARS = {
    "SURFACE": "--color-surface",
    "BG_SUBTLE": "--color-bg-subtle",
    "BG_INSET": "--color-bg-inset",
    "BORDER": "--color-border",
    "BORDER_STRONG": "--color-border-strong",
    "TEXT": "--color-text",
    "TEXT_SECONDARY": "--color-text-secondary",
    "TEXT_MUTED": "--color-text-muted",
    "ACCENT": "--color-accent",
    "ACCENT_TINT": "--color-accent-tint",
}


# --- resolve_category_color ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("color", "expected"),
    [
        ("blue", "#3457c4"),
        ("red", "#c0334a"),
        ("slate", "#5b6472"),
        (None, FALLBACK_CAT),
        ("", FALLBACK_CAT),
        ("bogus", FALLBACK_CAT),
        ("rebeccapurple", FALLBACK_CAT),
        ("#ABC", "#aabbcc"),
        ("#aabbcc", "#aabbcc"),
        ("#aabbccdd", "#aabbcc"),
    ],
)
def test_resolve_category_color(color: str | None, expected: str) -> None:
    assert resolve_category_color(color) == expected


def test_resolve_category_color_fallback_is_slate() -> None:
    assert FALLBACK_CAT == CAT_PALETTE["slate"]


# --- hex_to_rgb -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("hex_color", "expected_rgb"),
    [
        ("#000000", (0, 0, 0)),
        ("#ffffff", (255, 255, 255)),
        ("#ff0000", (255, 0, 0)),
        ("#f00", (255, 0, 0)),
        ("#3457c4", (0x34, 0x57, 0xC4)),
        ("#aabbccdd", (0xAA, 0xBB, 0xCC)),
    ],
)
def test_hex_to_rgb(hex_color: str, expected_rgb: tuple[int, int, int]) -> None:
    assert hex_to_rgb(hex_color) == expected_rgb


def test_hex_to_rgb_rgb_shorthand_round_trips_via_resolve_category_color() -> None:
    r, g, b = hex_to_rgb("#abc")
    assert resolve_category_color("#abc") == f"#{r:02x}{g:02x}{b:02x}"


# --- tag_gray -------------------------------------------------------------------------------


_HEX_RE = re.compile(r"^#[0-9a-f]{6}$")


def test_tag_gray_returns_valid_hex_for_many_indices() -> None:
    for index in range(20):
        color = tag_gray(index)
        assert _HEX_RE.match(color), color


def test_tag_gray_cycles() -> None:
    ramp_length = 5
    for index in range(ramp_length):
        assert tag_gray(index) == tag_gray(index + ramp_length)


def test_tag_gray_distinct_within_one_cycle() -> None:
    ramp_length = 5
    colors = {tag_gray(i) for i in range(ramp_length)}
    assert len(colors) == ramp_length


# --- drift guard: design/tokens.css must match the literal constants -----------------------


@pytest.mark.skipif(not TOKENS_CSS_PATH.exists(), reason="design/tokens.css not present")
def test_cat_palette_matches_tokens_css() -> None:
    css = TOKENS_CSS_PATH.read_text(encoding="utf-8")
    for key, value in CAT_PALETTE.items():
        match = re.search(rf"--cat-{key}-light:\s*(#[0-9a-fA-F]+);", css)
        assert match is not None, f"--cat-{key}-light not found in tokens.css"
        assert match.group(1).lower() == value.lower(), (
            f"CAT_PALETTE[{key!r}] = {value!r} drifted from tokens.css's "
            f"--cat-{key}-light = {match.group(1)!r}"
        )


@pytest.mark.skipif(not TOKENS_CSS_PATH.exists(), reason="design/tokens.css not present")
@pytest.mark.parametrize(("const_name", "css_var"), sorted(_SEMANTIC_TOKEN_CSS_VARS.items()))
def test_semantic_token_matches_tokens_css(const_name: str, css_var: str) -> None:
    import app.report_theme as report_theme

    css = TOKENS_CSS_PATH.read_text(encoding="utf-8")
    match = re.search(rf"{re.escape(css_var)}:\s*(#[0-9a-fA-F]+);", css)
    assert match is not None, f"{css_var} not found in tokens.css"
    const_value: str = getattr(report_theme, const_name)
    assert const_value.lower() == match.group(1).lower(), (
        f"report_theme.{const_name} = {const_value!r} drifted from tokens.css's "
        f"{css_var} = {match.group(1)!r}"
    )
