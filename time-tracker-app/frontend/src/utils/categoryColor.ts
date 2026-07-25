/**
 * Resolves a category's stored `color` value to a usable CSS colour. Per `app/schemas.py`
 * `CategoryCreate.color`, `color` is a free-form colour token: either one of the design system's
 * fixed 12 palette keys (`design/DESIGN_SYSTEM.md` §5.2, resolved to the theme-aware
 * `--cat-*` token from `design/tokens.css`) or a raw hex code (`#RGB`, `#RRGGBB`, or
 * `#RRGGBBAA`). Falls back to `slate` for anything else (invalid/unrecognized strings, or a
 * missing category) so the UI never breaks on an unexpected value.
 */
const KNOWN_KEYS = new Set([
  "red",
  "orange",
  "amber",
  "lime",
  "green",
  "teal",
  "cyan",
  "blue",
  "indigo",
  "violet",
  "pink",
  "slate",
]);

const HEX_COLOR_RE = /^#(?:[0-9a-f]{3}|[0-9a-f]{4}|[0-9a-f]{6}|[0-9a-f]{8})$/i;

export function categoryColorVar(colorKey: string | null | undefined): string {
  if (colorKey && KNOWN_KEYS.has(colorKey)) return `var(--cat-${colorKey})`;
  if (colorKey && HEX_COLOR_RE.test(colorKey)) return colorKey;
  return "var(--cat-slate)";
}

/** 16% tint background, per `design/DESIGN_SYSTEM.md` §5.2 chip-usage convention. */
export function categoryChipTint(colorKey: string | null | undefined): string {
  return `color-mix(in srgb, ${categoryColorVar(colorKey)} 16%, transparent)`;
}
