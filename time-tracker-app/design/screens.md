# Today + Week — Annotated Wireframes

Desktop-first (see DESIGN_SYSTEM.md §2 for the breakpoint plan). Layouts below assume a
`≥1024px` viewport with the nav rail + centered `1120px` content column. All spacing/sizes
reference tokens from `tokens.css`.

Legend: `[ ]` = interactive control, `( )` = chip, `▍` = category color bar, `●` = dot/status.

---

## 1. Today screen

### 1.1 Full layout (desktop, timer idle)

```
┌────┬──────────────────────────────────────────────────────────────────────┐
│ ⏱  │  Today · Mon, Jul 13                                                  │
│Today│──────────────────────────────────────────────────────────────────────│
│    │                                                                        │
│ 📅 │  ┌──────────────────────────────────────────────────────────────────┐ │
│Week│  │  What are you working on?                              [Start ▶]│ │
│    │  └──────────────────────────────────────────────────────────────────┘ │
│ 📊 │   (Category ▾)  #tag input…                                           │
│Repo│                                                                        │
│rts │   Recent:  (● Work) (● Deep work) (● Admin) (● Meetings)   +5 more     │
│ ⚙  │   Tags:    #client-a  #planning  #email  #followup           +8 more   │
│Sett│                                                                        │
│ing │  ──────────────────────────────────────────────────────────────────    │
│s   │                                                                        │
│    │  Today's entries                              Total: 3h 42m            │
│    │  ┌──────────────────────────────────────────────────────────────────┐ │
│    │  │▍Reviewed Q3 roadmap        (●Work)   #planning         1h 15m  ⋯ │ │
│    │  │▍Standup                    (●Meetings)                    15m  ⋯ │ │
│    │  │▍Fixed CI pipeline          (●Deep work) #ci #bugfix      2h 12m  ⋯ │ │
│    │  └──────────────────────────────────────────────────────────────────┘ │
└────┴──────────────────────────────────────────────────────────────────────┘
```

### 1.2 Full layout (desktop, timer running)

```
┌────┬──────────────────────────────────────────────────────────────────────┐
│    │  Today · Mon, Jul 13                                                  │
│    │──────────────────────────────────────────────────────────────────────│
│    │  ┌──────────────────────────────────────────────────────────────────┐ │
│    │  │ ● Tracking                                                        │ │
│    │  │ [ Writing quarterly report________________ ]                     │ │
│    │  │ (● Deep work ▾)   #reports #q3 [+]                                │ │
│    │  │                                                                    │ │
│    │  │              00:42:17                              [ Stop  ⏹ ]   │ │
│    │  └──────────────────────────────────────────────────────────────────┘ │
│    │                                                                        │
│    │   ⚠ Starting a new timer while one runs asks to stop-and-start ---    │
│    │     see 1.5 below.                                                    │
│    │                                                                        │
│    │  ──────────────────────────────────────────────────────────────────    │
│    │  Today's entries                          Total so far: 4h 24m         │
│    │  ┌──────────────────────────────────────────────────────────────────┐ │
│    │  │▍Reviewed Q3 roadmap        (●Work)   #planning         1h 15m  ⋯ │ │
│    │  │▍Standup                    (●Meetings)                    15m  ⋯ │ │
│    │  │▍Fixed CI pipeline          (●Deep work) #ci #bugfix      2h 12m  ⋯ │ │
│    │  └──────────────────────────────────────────────────────────────────┘ │
└────┴──────────────────────────────────────────────────────────────────────┘
```

### 1.3 Element inventory

| Element | Spec |
|---|---|
| Page header | `--text-lg` "Today", secondary text (`--color-text-muted`) "· Mon, Jul 13" (locale date, from `settings.timezone`). No primary button in header — the quick-add/timer card *is* the primary action, kept high on the page. |
| Quick-add / timer card | One card, two mutually-exclusive render modes: **idle** (1.1) or **running** (1.2). `--radius-lg`, `1px` border, idle = `--color-surface` bg; running = accent-tinted bg (`color-mix(in srgb, var(--color-accent) 6%, var(--color-surface))`) + `--shadow-sm`. |
| Title input (idle) | `44px` height oversized input (§8.2), placeholder `"What are you working on?"`. Autofocus on page load. |
| `[Start ▶]` button | Primary, `md` size, disabled until title has ≥1 non-whitespace character. Enter key in the title input = same action. Creates a `timer`-mode entry with `start_ts = now`. |
| Category picker (idle) | Inline `(Category ▾)` control docked under the input — optional at start time; can be set/changed later. Opens the same picker as recent-category chips (keyboard: `Tab` then `Enter`/arrow keys). |
| Tag input (idle) | Free-text with autocomplete against existing tags; `Enter` or `,` commits a chip; unknown tag text creates a new tag on save. |
| Recent categories row | Up to 6 most-recently-used categories as chips (§8.5/8.7). Clicking applies to the entry being started. `+N more` opens the full category list (popover). Keyboard: number keys `1`-`6` apply the Nth chip while focus is in the quick-add area. |
| Recent/favorite tags row | Same pattern, tags instead of categories; multi-select (click toggles on/off before starting). |
| Timer display (running) | `--text-timer`, `--font-mono`, `HH:MM:SS`, updates every second via local `setInterval` computed from `start_ts` (survives refresh — always derived from stored start time, never a client-only counter). `aria-live="polite"` region announces only start/stop, not per-tick. |
| Title/category/tags (running) | Editable in place while the timer runs — clicking the title turns it into a text input inline; no need to stop the timer to fix a typo or add a tag mid-task. |
| `[Stop ⏹]` button | Secondary/danger-tinted (§8.1), `md` size. Sets `end_ts = now`, computes `duration_minutes`, entry moves into "Today's entries" list immediately below with a brief highlight (`--motion-slow` background fade from accent-tint to normal). Keyboard shortcut `S` (see 1.6). |
| Today's entries list header | `--text-md` "Today's entries" + right-aligned running total (`--font-mono`, recalculates live if a timer is active, label changes to "Total so far" while tracking). |
| Entry rows | Per §8.3. Sorted reverse-chronological (most recent `start_ts` first). Clicking a row (not on the `⋯` menu) opens inline edit. `⋯` menu = Edit, Duplicate (prefill quick-add from this entry, common for repeat meetings), Delete (confirms via an inline "Delete? [Yes] [Cancel]" row swap, not a modal — keeps it fast). |
| Manual entry | Reached via the same quick-add card: a small `[+ Manual entry]` secondary link/button to the right of `[Start ▶]` (visible in idle state, hidden while a timer runs — you can still add a manual entry for a *different* time block while tracking live via the entries list's own `[+ Add entry]` affordity, see 1.4). Opens the title input plus two inline time fields (`start` / `end`, `--font-mono`, defaults: start = last entry's end time or now-1h, end = now) in place of the `[Start ▶]` button, which becomes `[Save]`. |

### 1.4 Empty state

When there are no entries yet today (and no timer running):

```
  Today's entries                                          Total: 0m

  ┌──────────────────────────────────────────────────────────────────┐
  │                                                                    │
  │        No entries yet today. Start a timer above, or             │
  │        [+ Add a manual entry] for something already done.        │
  │                                                                    │
  └──────────────────────────────────────────────────────────────────┘
```
Dashed `1px` border (`--color-border`), centered `--color-text-muted` text, `--space-6` vertical
padding. Not an illustration — this is a data tool, keep it text-only and low-key.

### 1.5 Conflict state — starting a timer while one is already running

Inline warning banner (not a modal — modals cost a click and this is a fast-entry tool):

```
  ┌──────────────────────────────────────────────────────────────────┐
  │ ⚠ A timer is already running ("Writing quarterly report").       │
  │   [Stop it and start this instead]     [Cancel]                  │
  └──────────────────────────────────────────────────────────────────┘
```
`--color-danger` icon/border tint on `--color-bg-subtle`. Confirms the deliberate choice; only
one live timer can exist at a time (matches the schema's single-entries-table model).

### 1.6 Keyboard shortcuts (Today)

| Key | Action |
|---|---|
| `/` or autofocus on load | Focus the quick-add title input |
| `Enter` (in title input, idle) | Start timer with current title/category/tags |
| `1`–`6` (focus in quick-add area) | Apply Nth recent category chip |
| `Shift+1`–`Shift+6` | Toggle Nth recent tag chip |
| `S` (focus not in a text field) | Toggle start/stop of the current/most recent timer |
| `M` | Jump to "Add manual entry" mode |
| `↑` / `↓` (focus in entries list) | Move focus between entry rows |
| `Enter` (entry row focused) | Open inline edit for that row |
| `E` (entry row focused) | Same as Enter — explicit edit shortcut |
| `Backspace`/`Delete` (entry row focused) | Open inline delete-confirm row |
| `Escape` (inline edit open) | Cancel edit, discard changes |
| `Cmd/Ctrl+Enter` (inline edit open) | Save edit from anywhere in the row |

### 1.7 Loading state

On initial mount (fetching today's entries + active-timer status from the API): the timer/quick-add
card renders in its idle skeleton (title input visible but disabled, no button state flash) and the
entries list shows 3 skeleton rows (`--color-bg-inset` blocks, `--radius-md`, subtle shimmer using
`--motion-slow`/`--ease-standard`, disabled under `prefers-reduced-motion`). No spinner — skeletons
match final layout so there's no reflow once data arrives.

---

## 2. Week screen

### 2.1 Full layout (desktop)

```
┌────┬──────────────────────────────────────────────────────────────────────┐
│    │  Week of Jul 7–13          [ ‹ ]  This week  [ › ]                    │
│    │──────────────────────────────────────────────────────────────────────│
│    │  ┌──────────────────────────────────┐ ┌───────────────────────────┐  │
│    │  │ Total this week          28h 42m  │ │ By category               │  │
│    │  │                                    │ │ [███ Work        ][██Adm]│  │
│    │  │  Mon  Tue  Wed  Thu  Fri  Sat  Sun │ │ ● Work        14h20  50%  │  │
│    │  │  5h2  6h1  4h5  7h0  3h9  1h5  0m  │ │ ● Meetings     6h05  21%  │  │
│    │  │  ▇▇▇  ▇▇▇  ▇▇   ▇▇▇▇ ▇▇   ▇    ·   │ │ ● Admin        4h50  17%  │  │
│    │  └──────────────────────────────────┘ │ ● Deep work    3h27  12%  │  │
│    │                                        │───────────────────────────│  │
│    │                                        │ By tag                    │  │
│    │                                        │ [███████░░░░░░░░░░░░]     │  │
│    │                                        │ #client-a     9h10  32%  │  │
│    │                                        │ #planning     5h40  20%  │  │
│    │                                        │ #ci           4h05  14%  │  │
│    │                                        │ (+ 6 more tags)           │  │
│    │                                        └───────────────────────────┘  │
│    │──────────────────────────────────────────────────────────────────────│
│    │  ▾ Monday, Jul 7                                            5h 20m    │
│    │  ┌──────────────────────────────────────────────────────────────────┐ │
│    │  │▍Sprint planning        (●Meetings)  #planning            55m  ⋯ │ │
│    │  │▍Fixed CI pipeline      (●Deep work) #ci #bugfix        2h 12m  ⋯ │ │
│    │  │▍Client A sync          (●Meetings)  #client-a            30m  ⋯ │ │
│    │  │▍Inbox zero             (●Admin)     #email             1h 43m  ⋯ │ │
│    │  └──────────────────────────────────────────────────────────────────┘ │
│    │  ▾ Tuesday, Jul 8                                           6h 10m    │
│    │  ┌──────────────────────────────────────────────────────────────────┐ │
│    │  │  … entry rows …                                                  │ │
│    │  └──────────────────────────────────────────────────────────────────┘ │
│    │  ▸ Wednesday, Jul 9                                          4h 50m   │
│    │  ▸ Thursday, Jul 10                                          7h 00m   │
│    │  ▸ Friday, Jul 11                                            3h 54m   │
│    │  ▸ Saturday, Jul 12                                          1h 05m   │
│    │  ▸ Sunday, Jul 13                                               0m    │
└────┴──────────────────────────────────────────────────────────────────────┘
```

### 2.2 Element inventory

| Element | Spec |
|---|---|
| Page header | `--text-lg` "Week of Jul 7–13" (respects `settings.week_starts_on`), `[‹]`/`[›]` ghost icon buttons to page weeks, "This week" secondary button to jump back to current (only shown when viewing a non-current week — replaces `[›]`'s disabled state on the latest week). |
| Summary card (left) | `--color-surface`, `--radius-lg`, `1px` border. Hero number `--text-xl` "Total this week". Below: a 7-column mini bar chart, one bar per day, height proportional to that day's total (max = tallest day), `--color-accent` fill at reduced opacity (this chart is time-of-week shape, not category — kept neutral so it doesn't compete with the category legend on the right); day totals in `--text-xs`/`--font-mono` above each bar. |
| Breakdown card (right) | Two stacked sections, `By category` then `By tag`, separated by a `1px` border. Each is the segmented bar + legend pattern from §8.8. Category legend sorted desc by duration, all categories shown (list is short by design — a personal tool won't have dozens). Tag legend shows top 3-5 with `(+N more tags)` expandable (click to show the rest inline, no navigation). |
| Day group header | `▾`/`▸` disclosure triangle (default: today and any day with entries expanded; empty future days collapsed), day name + date, right-aligned day total (`--font-mono`). Click anywhere on the header row toggles collapse. Keyboard: `Enter`/`Space` on focused header toggles. |
| Entry rows (within day group) | Identical component to Today (§8.3) — same row height, same `⋯` menu (Edit, Duplicate, Delete), so muscle memory transfers between screens. Editing here works the same inline pattern as Today. |
| Empty day | Day group still renders (so the week's shape stays legible) but shows `--color-text-muted` "No entries" instead of a row list, and its bar in the mini chart renders as a hairline instead of a filled bar. |
| Add entry to a past day | Each day-group header reveals a `[+ Add entry]` ghost button on hover/focus (mirrors the Today quick-add, but forces manual mode with `start`/`end` defaulting to a sensible gap in that day — e.g. after the last entry's end time). |

### 2.3 States

- **Loading:** summary card and breakdown card show skeleton blocks (bars replaced with
  `--color-bg-inset` placeholders); day groups show 2 skeleton rows each for the current day only,
  others collapsed-skeleton (just the header shimmer). Same no-reflow-on-load principle as Today.
- **Empty week** (new user / no entries at all yet): summary card shows "0m — nothing logged yet
  this week", breakdown card shows "No data yet — entries you log will show up here", every day
  group renders in its empty-day state (2.2 row above). No dead-end — a "Go to Today" secondary
  button sits in the summary card to route back to fast entry.
- **Active timer on Week screen:** if a timer is currently running (started from Today), a slim
  sticky banner appears just under the page header: `● Tracking "Writing quarterly report" — 00:42:17
  [Stop]` (`--color-accent` left border, `--color-bg-subtle` background) so the user is never blind
  to a running timer while reviewing the week. Clicking the banner navigates to Today; `[Stop]`
  stops it in place without navigating.

### 2.4 Keyboard shortcuts (Week)

| Key | Action |
|---|---|
| `←` / `→` | Previous / next week |
| `T` | Jump to current week |
| `↑` / `↓` | Move focus between day-group headers and, within an expanded group, entry rows |
| `Enter`/`Space` (day header focused) | Toggle expand/collapse |
| `Enter` (entry row focused) | Open inline edit |
| `A` (day header focused) | Add entry to that day |
| `Backspace`/`Delete` (entry row focused) | Inline delete-confirm |
| `Escape` | Close any open inline edit/confirm |

### 2.5 Responsive behavior

- **`768–1023px`:** the two-column summary/breakdown row (2.1) stacks to a single column — summary
  card first (it answers "how much, total"), breakdown card second, full width. Day groups unchanged.
- **`<768px`:** nav rail becomes a bottom tab bar; mini 7-bar day chart shrinks font but keeps 7
  columns (never drops to fewer days — weekly shape is the point); entry rows drop the tag-chip
  column onto a second line under the title if the row would otherwise overflow, category chip and
  duration stay on the primary line.

---

## 3. Cross-screen notes for the frontend-developer

- Entry row, category chip, tag chip, and the segmented-bar/legend pattern are **shared components**
  used identically on Today and Week — build them once.
- Duration formatting: always `H h MM m` for display (e.g. `1h 15m`, `45m`, `0m`); the live timer is
  the only place `HH:MM:SS` appears.
- All times are computed from stored UTC ISO-8601 `start_ts`/`end_ts` and localized client-side via
  `settings.timezone` — the design doesn't assume a specific date library, just that display always
  goes through one localization step.
- Every destructive action (delete) uses the inline confirm-row pattern (§1.3 `⋯` menu note) — no
  `window.confirm()`, no modal, consistent on both screens.
- Category and tag pickers (quick-add, entry inline-edit, manual-entry form) are the same popover
  component in all three call sites.
