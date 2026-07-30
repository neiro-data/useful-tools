# Webpage Time Tracker

## Resume

A personal **Tampermonkey userscript** (plain JavaScript, no build step, no dependencies) that
tracks how long you actually spend on time-sink websites and escalates nudges once you pass that
site's daily limit.

- **Stack:** one self-contained file — `webpage-time-tracker.user.js`. No `package.json`, no
  bundler, nothing to install beyond Tampermonkey itself. Alongside it, an optional Python
  (`uv` + Tkinter) settings app for managing the site list without editing the script.
- **Target:** Chrome (Tampermonkey). Personal use only — not published to any store.
- **Key idea:** every tracked site carries **its own daily limit**, and the counter for the site
  you're on is **always visible** — dimmed while you're under half of it, opaque as it climbs.
- **History:** 14 days of per-site totals are kept, so "am I improving?" is answerable. Nothing is
  enforced against history — it's for the trend only.

### Setup

1. Install [Tampermonkey](https://www.tampermonkey.net/) in Chrome.
2. Tampermonkey → Dashboard → **+** (new script) → paste the contents of
   `webpage-time-tracker.user.js` → save.
3. Visit a tracked site. The badge is there immediately, showing that site's used/limit.

Settings live in `~/.webpage-time-tracker/config.json` and are edited with the settings app below.
The `DEFAULTS` block at the top of the script is only the fallback for a fresh install with no
config yet.

### Settings app

```sh
uv run wtt-config          # from this folder
```

A small Tkinter window listing the registered sites with their favicon, domain, path and limit, plus
Add / Edit / Remove. Saving writes `config.json` atomically.

While the window is open it also serves that file at `http://127.0.0.1:8787/config.json` — loopback
only. The userscript fetches it in the background (at most once a minute across all tabs) and caches
it in Tampermonkey storage, so **the app does not need to be running** for the script to work; it
uses the last config it saw.

**After changing settings, reload the tab.** The tab you're on picks up new limits live, but a site
you just *added* was already ruled out at page load, so it needs a reload to start counting.

Icons come from each site's own `/favicon.ico`, fetched once and cached as PNG under
`~/.webpage-time-tracker/icons/`; anything that fails falls back to a drawn globe. No third-party
icon service is involved. Icons are GUI-only — the in-page badge stays text, so the host page's CSP
never enters into it.

The Add/Edit dialog's **Suggest** button proposes a host/path regex for a domain (an optional hint
narrows it, e.g. "only Shorts"). It checks a small built-in table first, then asks Claude on a miss,
using the Claude Code CLI (`claude`) — it must be installed and logged in. If the CLI isn't on `PATH`
and `ANTHROPIC_API_KEY` is set, it falls back to the `anthropic` SDK (install the `api` extra:
`uv sync --extra api`). Suggestions are validated and cached at
`~/.webpage-time-tracker/suggest-cache.json`.

#### Development

```sh
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
node --check webpage-time-tracker.user.js
```

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

Ratio is `time used on this site / this site's limit`. Each site climbs its own ladder — being over
on X does nothing to Shorts.

| Ratio | Behaviour |
|---|---|
| < 50% | Badge, bottom-right, dimmed |
| ≥ 50% | Badge at full opacity |
| ≥ 100% | Badge turns red + full-screen overlay, dismissible immediately |
| ≥ 125% | Overlay + 5s wait before Dismiss enables |
| ≥ 150% | Overlay + whole page goes grayscale + any `<video>` is paused |

Dismissing snoozes the overlay for `snoozeMinutes` (default 5) — without that the tool would be
unusable. The snooze is per site, and the badge stays visible while snoozed.

## Config

`~/.webpage-time-tracker/config.json`, written by the settings app. Same keys as the script's
`DEFAULTS` block.

| Key | Default | Meaning |
|---|---|---|
| `dayStartHour` | `4` | Local hour the day rolls over — 4am, not midnight, so the counter can't be waited out at 23:58 |
| `idleSeconds` | `60` | No input for this long and the clock stops |
| `snoozeMinutes` | `5` | How long a dismissed overlay stays gone |
| `historyDays` | `14` | Days of per-site totals kept before pruning |
| `sites` | Shorts 15, Reels 15, X 30 | `{ name, host, path?, limitMinutes }` — `host`/`path` are regex *source strings*, matched against `location.hostname` / `location.pathname`. Omit `path` to track a whole site |

Typing a domain in the app produces the host pattern (`youtube.com` → `(^|\.)youtube\.com$`, which
covers subdomains); an "advanced" toggle takes a hand-written regex instead. Both sides validate,
and the script skips a site whose pattern won't compile rather than dying on it.

The script's `@match` is `*://*/*` deliberately, so the site list lives in exactly one place; on any
hostname matching no site it bails out immediately and costs the page nothing.

## Tampermonkey menu

Available from the Tampermonkey icon while on a tracked site:

- **status** — today's used/limit per site, plus a 7-day all-sites trend
- **reset this site's counter** — the current site back to zero
- **grant 10 more minutes here** — deliberate override, current site only

## Notes and limits

- **Cross-origin state** uses `GM_setValue`, not `localStorage`. `localStorage` is per-origin and
  therefore cannot hold counters readable from YouTube, Instagram *and* X. Stored under
  `wtt.state.v2` as `{ days: { "YYYY-MM-DD": { "<site name>": seconds } } }`, pruned on read.
  Renaming a rule starts that site's history over.
- **SPA routing:** entering `youtube.com/shorts/…` fires no page load, so the script patches
  `history.pushState`/`replaceState` and listens to `popstate`. The per-second tick is a backstop if
  the patch doesn't take in Tampermonkey's sandbox.
- **This is a speed bump, not a lock.** Tampermonkey can be disabled in a couple of clicks. It works
  as a self-nudge, not as a commitment device.
- **Desktop only.** Deliberately — mobile browsers can't run this.

## Not implemented (v0.3)

Safari port (needs an Xcode app wrapper and lacks `chrome.idle`), MV3 extension, cross-machine sync,
usage charts, editing the global settings (`dayStartHour`, `idleSeconds`, …) from the GUI — the app
manages the site list only, the rest are still file-level values.
