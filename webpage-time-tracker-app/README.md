# Webpage Time Tracker

## Resume

A personal **Tampermonkey userscript** (plain JavaScript, no build step, no dependencies) that
tracks how long you actually spend on time-sink websites and escalates nudges once you pass a daily
budget.

- **Stack:** one self-contained file — `webpage-time-tracker.user.js`. No `package.json`, no
  bundler, nothing to install beyond Tampermonkey itself.
- **Target:** Chrome (Tampermonkey). Personal use only — not published to any store.
- **Key idea:** a *single pooled* budget across every tracked site, not one budget per site.
  45 minutes on YouTube Shorts and 45 on X is 90 minutes of the same problem.

### Setup

1. Install [Tampermonkey](https://www.tampermonkey.net/) in Chrome.
2. Tampermonkey → Dashboard → **+** (new script) → paste the contents of
   `webpage-time-tracker.user.js` → save.
3. Visit a tracked site. Nothing appears until you're at 50% of budget.

To change settings, edit the `CONFIG` block at the top of the script and save.

## How time is counted

Tab-open time is meaningless — a backgrounded tab would rack up hours. A second only counts when
**all** of these hold:

- the tab is visible (`visibilityState === 'visible'`)
- the browser window itself is focused (`document.hasFocus()`) — alt-tabbing to another app stops
  the clock
- there's been input in the last `idleSeconds`
- the current URL matches a rule

Because only one tab is ever visible *and* focused, two open tracked tabs can't double-count.

Elapsed time is measured from real timestamps and clamped to twice the tick, so closing the laptop
for two hours doesn't inject two hours of "usage".

## Escalation ladder

Ratio is `time used / budget`.

| Ratio | Behaviour |
|---|---|
| ≥ 50% | Small badge, bottom-right |
| ≥ 100% | Full-screen overlay, dismissible immediately |
| ≥ 125% | Overlay + 5s wait before Dismiss enables |
| ≥ 150% | Overlay + whole page goes grayscale + any `<video>` is paused |

Dismissing snoozes the overlay for `snoozeMinutes` (default 5) — without that the tool would be
unusable. The badge stays visible while snoozed.

## Config

All in the `CONFIG` block at the top of the script.

| Key | Default | Meaning |
|---|---|---|
| `budgetMinutes` | `45` | Total daily budget, pooled across all rules |
| `dayStartHour` | `4` | Local hour the day rolls over — 4am, not midnight, so the counter can't be waited out at 23:58 |
| `idleSeconds` | `60` | No input for this long and the clock stops |
| `snoozeMinutes` | `5` | How long a dismissed overlay stays gone |
| `rules` | Shorts, Reels, X | `{ name, host, path? }` — regexes against `location.hostname` / `location.pathname`. Omit `path` to track a whole site |

Adding a site means adding one entry to `rules`. The script's `@match` is `*://*/*` deliberately so
the site list lives in exactly one place; on any hostname matching no rule it bails out on the first
line and costs the page nothing.

## Tampermonkey menu

Available from the Tampermonkey icon while on a tracked site:

- **status** — how much of today's budget is used
- **reset today's counter** — back to zero
- **grant 10 more minutes** — deliberate override

## Notes and limits

- **Cross-origin state** uses `GM_setValue`, not `localStorage`. `localStorage` is per-origin and
  therefore cannot hold a counter shared between YouTube, Instagram and X.
- **SPA routing:** entering `youtube.com/shorts/…` fires no page load, so the script patches
  `history.pushState`/`replaceState` and listens to `popstate`. The per-second tick is a backstop if
  the patch doesn't take in Tampermonkey's sandbox.
- **This is a speed bump, not a lock.** Tampermonkey can be disabled in a couple of clicks. It works
  as a self-nudge, not as a commitment device.
- **Desktop only.** Deliberately — mobile browsers can't run this.

## Not implemented (v0.1)

Safari port (needs an Xcode app wrapper and lacks `chrome.idle`), MV3 extension, options UI,
per-site budgets, usage history/charts, cross-machine sync.
