"""Literal design-token constants for report exports (HTML/PDF/Markdown).

Transcribed by hand from ``design/tokens.css`` (light theme only — reports are always rendered
light, regardless of the viewer's OS theme). ``design/`` lives outside the ``app`` package, so
these values are copied as literals rather than parsed from CSS at runtime.

Category color resolution (``resolve_category_color``) mirrors
``frontend/src/utils/categoryColor.ts``'s ``categoryColorVar``: a stored category ``color`` is
either one of the 12 fixed palette keys, a raw hex code (``#RGB``/``#RRGGBB``/``#RRGGBBAA``), or
anything else, which falls back to ``slate``.
"""

import re

# --- Semantic tokens (light theme) --------------------------------------------------------------

SURFACE = "#ffffff"
BG_SUBTLE = "#f7f8fa"
BG_INSET = "#eef0f3"
BORDER = "#e2e5e9"
BORDER_STRONG = "#c7cdd6"

TEXT = "#12151a"
TEXT_SECONDARY = "#454c56"
TEXT_MUTED = "#767f8a"

ACCENT = "#2f5bd7"
ACCENT_TINT = "#eaf0fe"

# --- Category palette (light-theme hues) --------------------------------------------------------

CAT_PALETTE: dict[str, str] = {
    "red": "#c0334a",
    "orange": "#b25a17",
    "amber": "#96660a",
    "lime": "#5c7a1b",
    "green": "#22795b",
    "teal": "#1b7a78",
    "cyan": "#1a6fa0",
    "blue": "#3457c4",
    "indigo": "#5a4fcf",
    "violet": "#8034b8",
    "pink": "#c13584",
    "slate": "#5b6472",
}

FALLBACK_CAT = CAT_PALETTE["slate"]

# --- Layout / typography ---------------------------------------------------------------------

RADIUS_PX = 8

FONT_SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
FONT_MONO = "'SF Mono', ui-monospace, 'Cascadia Code', Menlo, Consolas, monospace"

TEXT_XS = 12
TEXT_SM = 13
TEXT_BASE = 14
TEXT_MD = 16
TEXT_LG = 20
TEXT_XL = 28

_HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")

_TAG_GRAY_RAMP = (
    "#454c56",
    "#5b6472",
    "#767f8a",
    "#9aa2ac",
    "#c7cdd6",
)


def resolve_category_color(color: str | None) -> str:
    """Resolve a stored category ``color`` value to a literal hex color, mirroring
    ``categoryColorVar`` in ``frontend/src/utils/categoryColor.ts``.

    ``color`` is either one of the 12 fixed palette keys (see ``CAT_PALETTE``) or a raw hex code
    (``#RGB``/``#RRGGBB``/``#RRGGBBAA``, alpha stripped). Anything else -- ``None``, empty, a CSS
    color name, or an unrecognized string -- falls back to ``FALLBACK_CAT`` (slate).
    """
    if color and color in CAT_PALETTE:
        return CAT_PALETTE[color]
    if color and _HEX_COLOR_RE.match(color):
        r, g, b = hex_to_rgb(color)
        return f"#{r:02x}{g:02x}{b:02x}"
    return FALLBACK_CAT


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Expand a ``#RGB``/``#RRGGBB``/``#RRGGBBAA`` hex string to an ``(r, g, b)`` 0-255 tuple
    (alpha, if present, is dropped)."""
    value = hex_color.lstrip("#")
    if len(value) in (3, 4):
        value = "".join(ch * 2 for ch in value[:3])
    else:
        value = value[:6]
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def tag_gray(index: int) -> str:
    """Neutral grayscale hex for the ``index``-th tag segment, cycling through a fixed ramp (tags
    have no stored color, unlike categories)."""
    return _TAG_GRAY_RAMP[index % len(_TAG_GRAY_RAMP)]


def mix_with_surface(hex_color: str, pct: int = 16) -> str:
    """Mix ``hex_color`` at ``pct``% into ``SURFACE``, approximating CSS
    ``color-mix(in srgb, hex_color pct%, transparent)`` composited over a white surface (Outlook
    can't evaluate ``color-mix()`` at render time, so this is precomputed to a literal hex)."""
    r, g, b = hex_to_rgb(hex_color)
    sr, sg, sb = hex_to_rgb(SURFACE)
    fraction = pct / 100
    mixed_r = round(r * fraction + sr * (1 - fraction))
    mixed_g = round(g * fraction + sg * (1 - fraction))
    mixed_b = round(b * fraction + sb * (1 - fraction))
    return f"#{mixed_r:02x}{mixed_g:02x}{mixed_b:02x}"
