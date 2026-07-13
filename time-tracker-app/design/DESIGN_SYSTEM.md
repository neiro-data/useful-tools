# Time Tracker — Design System

Personal, offline-first time tracker. Single technical user, desktop-first, keyboard-driven.
V1 optimizes for **speed of data entry** first, clarity second, visual polish third — but every
decision here is built to extend cleanly (more screens, more themes, more chart types) without a
redesign.

---

## 1. Design principles

1. **Fewest clicks/keystrokes to log time.** Every primary action (start timer, quick-add entry,
   pick a category/tag) must be reachable without leaving the keyboard and without a modal unless
   truly necessary.
2. **One glanceable truth.** Color = category, always. The same category always renders the same
   color in every screen, in both themes. Tags are secondary (monochrome chips), so category color
   stays the one strong visual signal.
3. **Data-dense, not cluttered.** This is a personal tool, not a marketing product — favor compact
   rows and real information (durations, running totals) over whitespace-for-its-own-sake. But keep
   a consistent spacing rhythm so density reads as "organized," not "cramped."
4. **Text-first, chrome-last.** Native form controls, system font stack, minimal iconography (a
   small inline SVG icon set is fine; no icon font, no illustration).
5. **Theme is a rendering detail, not a redesign.** Light and dark share the same tokens,
   component structure, and spacing — only color values swap. Respect `prefers-color-scheme`; no
   manual toggle required for V1 (documented as a future Settings option).
6. **Accessible by default.** WCAG 2.1 AA contrast minimums for all text and meaningful color use;
   category color is always paired with a text label or shape, never color alone.

---

## 2. Layout grid

- **Base unit:** 8px grid (all spacing/sizing is a multiple of 4px, with 8px as the primary step).
- **Content container:** max-width `1120px`, centered, with `24px` side padding below 1120px
  viewport width.
- **Desktop-first structure**, single persistent left nav rail + content area:

```
┌───────────┬────────────────────────────────────────────────┐
│           │  Page header (title + primary action)           │
│  Nav rail │──────────────────────────────────────────────────│
│  72px     │  Content (max-width 1120px, centered)            │
│  (icons + │                                                  │
│  labels)  │                                                  │
│           │                                                  │
└───────────┴────────────────────────────────────────────────┘
```

- Nav rail: fixed `72px` wide (icon + 10px label, stacked), full height, contains: Today, Week,
  Reports, Settings. Active item = filled icon + accent-colored left bar (4px) + accent text.
- **Breakpoints:**
  - `≥1024px` — full two-column layouts where specified (e.g. Week: list + breakdown panel).
  - `768–1023px` — single column, breakdown panel moves below/collapses into an accordion.
  - `<768px` — nav rail collapses to a bottom tab bar (4 icons); content full-width with 16px
    padding. (V1 is desktop-first; this is documented behavior, not the primary target.)

---

## 3. Spacing scale

Token name `--space-N`, 4px base unit:

| Token | Value | Typical use |
|---|---|---|
| `--space-1` | 4px | icon-to-label gaps, chip internal padding (vertical) |
| `--space-2` | 8px | tight stacks, chip internal padding (horizontal), input padding-y |
| `--space-3` | 12px | input padding-x, row internal padding |
| `--space-4` | 16px | default gap between related elements, card padding |
| `--space-5` | 24px | gap between distinct sections/groups |
| `--space-6` | 32px | page header spacing, major section separation |
| `--space-8` | 48px | large layout gutters (nav rail content offset) |
| `--space-10` | 64px | page top padding on wide viewports |

Rule of thumb: **4/8px** inside components, **16px** between components in a group, **24–32px**
between groups/sections.

---

## 4. Typography scale

System font stack (no web font loading, no FOUT, works instantly offline):

```
--font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
--font-mono: "SF Mono", ui-monospace, "Cascadia Code", Menlo, Consolas, monospace;
```

Monospace is used specifically for **durations and timestamps** (tabular figures, so numbers don't
jitter as a live timer ticks and columns of times align).

| Token | Size | Weight | Line-height | Use |
|---|---|---|---|---|
| `--text-xs` | 12px | 500 | 16px | metadata, tag chip labels, timestamps |
| `--text-sm` | 13px | 400/500 | 18px | secondary text, table/list labels |
| `--text-base` | 14px | 400 | 20px | body text, inputs, entry titles |
| `--text-md` | 16px | 500 | 22px | section headers, entry row primary text |
| `--text-lg` | 20px | 600 | 26px | page titles ("Today", "Week of Jul 7") |
| `--text-xl` | 28px | 600 | 34px | totals hero number (e.g. week total hours) |
| `--text-timer` | 40px | 600 | 1 | live running-timer display (monospace, tabular-nums) |

Weight scale: 400 (regular), 500 (medium — default for UI labels/buttons), 600 (semibold — headers,
emphasis). No bold (700) in V1; keep the palette of weights small.

---

## 5. Color system

### 5.1 Structure

Colors are defined as **semantic tokens** layered over **primitive scales**, so light/dark just
remaps which primitive a semantic token points to. See `tokens.css` for the literal values.

Semantic roles:

- `--color-bg` / `--color-bg-subtle` / `--color-bg-inset` — page background, card background,
  recessed areas (input backgrounds, hover rows).
- `--color-surface` — raised surface (cards, popovers).
- `--color-border` / `--color-border-strong` — hairlines, input borders.
- `--color-text` / `--color-text-secondary` / `--color-text-muted` — primary/secondary/tertiary
  text.
- `--color-accent` / `--color-accent-hover` / `--color-accent-text-on` — the app's single brand
  accent (used for the active nav item, primary buttons, focus rings, the running-timer pulse).
  Accent is **not** used for categories — it's reserved for "the app," so it never collides with
  category color meaning.
- `--color-danger` / `--color-danger-bg` — delete affordances, destructive confirmation.
- `--color-success` — used sparingly (e.g. "saved" toast).

### 5.2 Category color palette

Categories are user-created with an arbitrary count, but color must (a) stay legible as text/on
chips in both themes, and (b) be visually distinct enough at a glance in charts. V1 ships a **fixed
palette of 12 named hues**; when creating a category the user picks one of the 12 (not a free hex
picker) — this guarantees every category color has been pre-tuned for AA contrast in both themes.
(A custom-hex escape hatch can be added later as `category.color = 'custom:#rrggbb'` without
breaking this scheme — see Section 5.4.)

The 12 hues (`--cat-*` tokens), chosen for hue-separation (~30° apart on the color wheel) so
adjacent categories never look ambiguous in a legend or stacked bar:

| Key | Name | Light-theme swatch (text/icon use) | Dark-theme swatch |
|---|---|---|---|
| `red` | Red | `#C0334A` | `#F26E85` |
| `orange` | Orange | `#B25A17` | `#F2A65A` |
| `amber` | Amber | `#96660A` | `#E8B84B` |
| `lime` | Lime | `#5C7A1B` | `#B3D661` |
| `green` | Green | `#22795B` | `#5FCB9E` |
| `teal` | Teal | `#1B7A78` | `#5AD0CC` |
| `cyan` | Cyan | `#1A6FA0` | `#5EC3F0` |
| `blue` | Blue | `#3457C4` | `#7FA0F5` |
| `indigo` | Indigo | `#5A4FCF` | `#A79BFF` |
| `violet` | Violet | `#8034B8` | `#CC8CF0` |
| `pink` | Pink | `#C13584` | `#F291C4` |
| `slate` | Slate/Grey | `#5B6472` | `#AEB7C2` |

Each swatch was chosen so:
- **Text/icon usage** (the color value itself, used as text color or a solid dot/icon) meets
  **≥4.5:1** contrast against that theme's `--color-bg`/`--color-surface`.
- **Chip usage**: category chips render as `color-mix(in srgb, <cat-color> 16%, transparent)`
  background with the same `<cat-color>` as text/border — background tint is decorative only
  (not relied on for contrast), text carries the AA guarantee.
- Dark-theme values are the same hue rotated to a lighter/more saturated tone (not just "the same
  hex over a dark bg") specifically so they independently clear AA on dark backgrounds rather than
  inheriting light-theme values that would fail.

Category color is **never the sole indicator** — every category also always shows as a text label
(name) alongside the color dot/chip, satisfying WCAG 1.4.1 (use of color).

### 5.3 Chart/breakdown usage

For the Week screen's category breakdown (segmented bar / donut), each segment uses the *chip*
tint (16% mix) as fill and the solid `--cat-*` value as the border/label color — this keeps large
color fields softer (less visually loud for a data-dense screen) while keeping labels/legend fully
AA-compliant.

### 5.4 Future extensibility (not built in V1, but don't block it)

- A "custom color" escape hatch: allow `category.color` to store either a palette key (`"blue"`) or
  a literal hex (`"#2A9D8F"`); the UI computes light/dark-safe variants at render time via
  relative-luminance clamping. Out of scope for V1 — the fixed 12 are enough for a personal tool.
- A true theme toggle (persisted override of `prefers-color-scheme`) — token structure already
  supports this (see `tokens.css` comment), just needs a `data-theme` attribute switch in the app.

---

## 6. Elevation & shape

- **Radius:** `--radius-sm` 4px (chips, small buttons), `--radius-md` 8px (inputs, cards, rows),
  `--radius-lg` 12px (modals/popovers, the timer widget).
- **Shadows** are minimal and only used for genuinely floating elements (popovers, dropdowns,
  modal), never for flat cards/rows — cards are distinguished by background + 1px border, not
  shadow, to keep the dense list views calm.
  - `--shadow-sm`: subtle 1px-ish separation for dropdowns.
  - `--shadow-md`: popovers/modals.
- **Borders:** 1px hairline (`--color-border`) is the default separator between rows/sections
  rather than shadow or heavy spacing — keeps dense lists compact.

---

## 7. Motion

- Durations: `--motion-fast` 100ms (hover/press feedback), `--motion-base` 160ms (expand/collapse,
  chip select), `--motion-slow` 240ms (modal/popover enter).
- Easing: `--ease-standard: cubic-bezier(0.2, 0, 0, 1)` for enter/expand,
  `--ease-out: cubic-bezier(0, 0, 0.2, 1)` for exits.
- The **running timer** does not animate its digits (no per-second flip/slide) — it just re-renders
  the text every second via `tabular-nums`, to avoid distracting motion during focused work; only
  a subtle pulsing dot (`--motion-slow`, opacity 1↔0.4, 2s loop) next to "Tracking…" indicates
  liveness. Respects `prefers-reduced-motion` (pulse becomes static, no opacity animation).

---

## 8. Component patterns

### 8.1 Buttons

Three visual variants, one size scale (this is a compact tool, not a marketing site):

- **Primary** (`--color-accent` bg, `--color-accent-text-on` text) — one per view max (e.g. "Start
  timer", "Save entry").
- **Secondary** (transparent bg, `--color-border-strong` border, `--color-text` text) — "Cancel",
  "Add manual entry".
- **Ghost/icon** (no bg/border until hover, then `--color-bg-inset`) — row-level actions (edit,
  delete, more).
- **Danger** (text/icon `--color-danger`, ghost by default, `--color-danger-bg` on hover/confirm) —
  delete.

Sizes: `sm` (28px height, `--text-sm`, used inline in rows) and `md` (36px height, `--text-base`,
used in headers/forms). Height, not padding-only, is fixed so buttons align on a row baseline.

States: default, hover (background shift), active/pressed (slightly darker + scale 0.98 via
`--motion-fast`), focus-visible (2px `--color-accent` outline, 2px offset — always visible on
keyboard nav, never suppressed), disabled (0.5 opacity, no pointer events).

### 8.2 Inputs

Single-line text inputs, `36px` height, `--radius-md`, `--color-bg-inset` background,
`--color-border` border (1px), `--color-border-strong` + `--color-accent` 2px ring on focus.
Padding `0 var(--space-3)`. Placeholder = `--color-text-muted`.

- **Quick-add input** (Today screen) is the one oversized exception: `44px` height, `--text-md`,
  to signal "this is the primary action of the page."
- **Duration/time inputs** use `--font-mono` + tabular-nums.
- Inline validation: red 1px border (`--color-danger`) + small helper text below, not a modal.

### 8.3 Entry row

The core repeating unit on both Today and Week. Single-line by default, expands only on edit.

```
┌─┬──────────────────────────────┬───────────┬─────────────┬────────┬────┐
│▍│ Entry title                  │ [category]│ #tag #tag   │ 45m    │ ⋯  │
└─┴──────────────────────────────┴───────────┴─────────────┴────────┴────┘
 4px       flex, truncate         chip         chips, wrap    mono,   menu
 category                                                     right   (edit/
 color bar                                                    aligned  delete)
```

- Left `4px` vertical bar = category color (the row's fast-scan color signal; independent of the
  chip, so color reads even when the row is dense/scrolled fast).
- Height: `40px` collapsed (list density), `--space-2` vertical padding.
- Hover: `--color-bg-inset` background, reveals the `⋯` action menu (hidden until hover/focus to
  reduce visual noise; always reachable via keyboard focus/Tab).
- Click title or press `Enter` while row focused → inline edit (row grows, title becomes a text
  input, category/tag chips become pickers, Escape cancels/Enter saves).
- Duration column is always `--font-mono`, right-aligned, so a column of durations aligns on the
  decimal/digit.
- Running entry (if this row is the active timer, shown in "recent entries" once stopped—see Today
  spec) uses `--color-accent` for the bar instead of category color while live, plus the pulse dot.

### 8.4 Timer widget (Today screen hero)

```
┌───────────────────────────────────────────────────┐
│  ● Tracking                                         │
│  Writing quarterly report                           │
│  [Category ▾]  #tags…                               │
│                                                      │
│              00:42:17                    [ Stop ]   │
└───────────────────────────────────────────────────┘
```

- Idle state (no timer running): same card shape, replaced with the quick-add form + a prominent
  "Start timer" button — see `screens.md`.
- Active state: `--color-accent`-tinted card background (`color-mix(accent 6%, surface)`),
  `--radius-lg`, `--shadow-sm`. Big monospace time (`--text-timer`), a labeled pulse dot, editable
  title/category/tags *while running* (no need to stop to fix a typo), and a single `Stop` button
  (danger-tinted secondary, since stopping is a deliberate but not destructive action).
- Keyboard: `S` starts/stops the timer when focus isn't in a text field (global shortcut,
  documented in `screens.md`).

### 8.5 Category chip

```
( ● Work )     ← default (unselected, in a picker list)
[ ● Work ]     ← selected/applied (filled tint, border = solid color)
```

- Height `24px`, `--radius-sm` (pill-ish but not fully round — 4px keeps it calm, distinguishes
  from tag chips which *are* fully rounded, see 8.6), `--text-xs`, `--space-1`/`--space-2` padding.
- Dot (`8px` solid circle, `--cat-*` color) + label. Background = 16% tint of category color when
  applied/selected; transparent + `--color-border` outline when shown as a picker option.
- One category per entry (single-select), so this always renders as at most one chip per row.

### 8.6 Tag chip

```
#deep-work   ← plain, monochrome, --color-text-secondary
```

- Fully rounded (`--radius-lg`/pill), `--color-bg-inset` background, `--color-text-secondary` text,
  no per-tag color (tags are intentionally monochrome so they never compete with category color for
  attention — multiple tags per entry is expected, so noise must stay low).
- Selected/applied state (in the tag picker) adds a `--color-accent` 1px border + `--color-text`
  (darker/brighter) text, no fill change — enough to show "on" without introducing a second color
  language.
- Removable variant (in edit mode) shows a small `×` at `--space-1` from the label, `--color-danger`
  on hover.

### 8.7 Recent/favorite category & tag rail (Today, quick-add)

A single horizontal row of the **N most-recently-used** categories (chips) followed by the **N
most-recently-used** tags (chips), directly under the quick-add input. Click = apply to the entry
being created; number keys `1–9` apply the Nth chip for pure-keyboard entry. This is the primary
"fast selection" affordance called out in the brief.

### 8.8 Totals bar / segmented breakdown (Week)

Horizontal **segmented bar**, one segment per category, width proportional to share of total time:

```
[███ Work 62% ][██ Meetings 21%][█ Admin 17%]
```

- Height `12px`, `--radius-sm`, segments use the category's chip-tint fill with a 1px solid
  `--cat-*` divider between segments (so adjacent similar-hue segments still visually separate even
  before contrast differences are perceptible).
- A legend row below (wraps): color dot + name + total duration + percentage, sorted descending by
  time — this is what carries the AA-guaranteed text/contrast, the bar itself is a supporting visual
  only (never the sole source of the information, per WCAG 1.4.1).
- A parallel, smaller **by-tag** breakdown reuses the same bar pattern but renders in a flat neutral
  gray scale (opacity steps, not hue) since tags are monochrome by design (8.6) — this also visually
  differentiates "by category" (the primary, colorful breakdown) from "by tag" (secondary, quieter)
  at a glance.

---

## 9. Accessibility checklist (applies to Today + Week)

- All 12 category colors verified ≥4.5:1 as text/icon color against both themes' `--color-bg` and
  `--color-surface` (see Section 5.2 table + `tokens.css` values).
- Color is never the only signal: category = dot **and** label; tag selection state = border
  **and** weight change; running timer = pulse dot **and** the word "Tracking" **and** motion (with
  `prefers-reduced-motion` fallback).
- All interactive elements have a visible `:focus-visible` ring (2px accent, 2px offset); tab order
  follows visual order (quick-add → recent chips → timer controls → entry list → nav).
- Every icon-only control (row `⋯` menu, chip `×`) has an `aria-label`; decorative dots/bars have
  `aria-hidden="true"` with the text label carrying the semantics.
- Minimum hit target `24×24px` for chip `×`/inline icons, `36×36px` for standalone icon buttons.
- Live timer updates use `aria-live="polite"` on a container announcing state changes (started/
  stopped), not the per-second tick (which would spam screen readers).

---

## 10. File map

- `design/DESIGN_SYSTEM.md` — this file.
- `design/tokens.css` — literal CSS custom properties (light default + `prefers-color-scheme: dark`
  override), importable as-is by the React app (e.g. `import './design/tokens.css'` or copied into
  `src/styles/`).
- `design/screens.md` — Today + Week wireframes, states, and interaction/keyboard-shortcut spec.
