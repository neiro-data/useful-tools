/**
 * Resolves a category's stored `color` value to the design system's `--cat-*` token (see
 * `design/tokens.css` §Category color primitives). V1 categories are created by picking one of
 * the fixed 12 palette keys (`design/DESIGN_SYSTEM.md` §5.2), so `color` is expected to already be
 * one of these keys (e.g. `"blue"`). Falls back to `slate` for anything unrecognized (e.g. a
 * future free-hex value, or a missing category) so the UI never breaks on an unexpected value.
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

export function categoryColorVar(colorKey: string | null | undefined): string {
  const key = colorKey && KNOWN_KEYS.has(colorKey) ? colorKey : "slate";
  return `var(--cat-${key})`;
}

/** 16% tint background, per `design/DESIGN_SYSTEM.md` §5.2 chip-usage convention. */
export function categoryChipTint(colorKey: string | null | undefined): string {
  return `color-mix(in srgb, ${categoryColorVar(colorKey)} 16%, transparent)`;
}
