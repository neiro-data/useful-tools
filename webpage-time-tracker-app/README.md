# Webpage Time Tracker

## Resume

A personal **userscript** (plain JavaScript, no dependencies) that tracks how long you actually
spend on time-sink websites and escalates nudges once you pass that site's daily limit.

- **Stack:** a shared core plus a thin per-platform adapter in `src/`, concatenated into two
  ready-to-install userscripts in `dist/` by a stdlib-only Python script. No `package.json`, no
  bundler, no runtime dependencies. Alongside it, an optional Python (`uv` + Tkinter) settings app
  for managing the site list without editing the script.
- **Target:** Chrome (Tampermonkey) and Safari (Userscripts.app). Personal use only — not published
  to any store.
- **Key idea:** every tracked site carries **its own daily limit**, and the counter for the site
  you're on is **always visible** — dimmed while you're under half of it, opaque as it climbs.
- **History:** 14 days of per-site totals are kept, so "am I improving?" is answerable. Nothing is
  enforced against history — it's for the trend only.

### Setup

**Chrome**

1. Install [Tampermonkey](https://www.tampermonkey.net/) in Chrome.
2. Tampermonkey → Dashboard → **+** (new script) → paste the contents of
   `dist/webpage-time-tracker.user.js` → save.
3. Visit a tracked site. The badge is there immediately, showing that site's used/limit.

**Safari**

1. Install [Userscripts](https://github.com/quoid/userscripts) (free, App Store) and enable it in
   Safari → Settings → Extensions.
2. Open the Userscripts toolbar popup, create a new script, and paste the contents of
   `dist/webpage-time-tracker.safari.user.js`. (You can also drop the file straight into whichever
   scripts directory you pointed the extension at in its settings — the location is one *you* pick,
   there is no fixed path to copy to.)
3. Visit a tracked site.
4. Run the checklist under *Verifying the Safari install* below — two of its assumptions are
   Safari-specific and worth confirming once.

The Safari build differs in three ways, all handled by its adapter: storage is promise-based rather
than synchronous, it declares `@inject-into content` (Userscripts.app exposes the `GM.*` APIs only
to the content world — see the note below), and it omits `@connect` (which Safari has no equivalent
for). If Safari's local-network policy blocks the loopback settings server, the script falls back to
its cached config and backs off its polling rather than failing.

> **`@inject-into content` is load-bearing.** With `page`, every `GM.*` call throws, the adapter
> swallows it, and the script silently runs on its baked-in `DEFAULTS`: the badge counts, but
> nothing persists across a reload and the settings app is never contacted. The adapter now logs a
> single `[wtt] GM storage unavailable` warning if that ever recurs. The cost of `content` is that
> the `history.pushState` patch no longer sees the page's navigations; the 1s tick already
> re-derives the active rule from `location.pathname`, so SPA routing is still picked up.

#### Verifying the Safari install

Reinstalling? Delete the old script in Userscripts first — a stale copy under the same name shadows
the new one.

1. **GM is live.** Safari → Settings → Advanced → *Show features for web developers*. On a tracked
   site, Develop → Show JavaScript Console, then reload. There must be **no** `[wtt] GM storage
   unavailable` warning.
2. **Counts persist.** Spend ~60s on a tracked site (window focused, mouse moving), note the badge,
   reload. It must resume at roughly the same number, not `0m`.
3. **State is shared across origins.** Visit a second tracked site, then return to the first — the
   first site's number must still be there. The per-site counter design rests on this.
4. **Start the settings app** (`uv run wtt-config`) and leave the window open.
5. **The server is reachable.** Open `http://127.0.0.1:8787/config.json` in a Safari tab; you should
   see JSON. If macOS asks for *Local Network* access, allow it (System Settings → Privacy &
   Security → Local Network → Safari). If this fails, the script is fine — it just stays on its
   cached config.
6. **The GUI drives the timer.** With a tracked tab already open and *not* reloaded, change that
   site's limit in the app and save. Within 30s the badge's denominator must change on its own, and
   going over must fire the overlay.
7. Adding a *brand-new* site still needs a tab reload — by design; the host early-out already ran.

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

Edit `src/`, never `dist/` — `dist/` is generated, and a test asserts it matches a fresh render of
`src/`, so a stale `dist/` fails the suite.

```sh
uv run python tools/build.py            # regenerate dist/ after any src/ change
uv run python tools/build.py --check    # verify dist/ is current, write nothing
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
node --check dist/webpage-time-tracker.user.js
node --check dist/webpage-time-tracker.safari.user.js
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

## Menu

Click the badge on a tracked site. The menu renders inside the script's own closed shadow root, so
it works identically on both browsers:

- **status** — today's used/limit per site, plus a 7-day all-sites trend
- **reset this site's counter** — the current site back to zero
- **grant 10 more minutes here** — deliberate override, current site only

On Chrome the same three commands are *also* registered in the Tampermonkey icon menu. Safari's
Userscripts.app has no equivalent API, which is why the badge menu exists.

## Notes and limits

- **Cross-origin state** uses the userscript host's own storage, not `localStorage`. `localStorage`
  is per-origin and therefore cannot hold counters readable from YouTube, Instagram *and* X. Stored
  under `wtt.state.v2` as `{ days: { "YYYY-MM-DD": { "<site name>": seconds } } }`, pruned on read.
  Renaming a rule starts that site's history over.
- **Storage writes are serialized** through a single promise chain. Safari's API is asynchronous, so
  without it two overlapping writes could interleave and silently drop counted seconds. One
  consequence: a write in flight when the tab unloads may not land, costing at most ~6s.
- **SPA routing:** entering `youtube.com/shorts/…` fires no page load, so the script patches
  `history.pushState`/`replaceState` and listens to `popstate`. The per-second tick is a backstop if
  the patch doesn't take in the host's sandbox.
- **This is a speed bump, not a lock.** The userscript host can be disabled in a couple of clicks.
  It works as a self-nudge, not as a commitment device.
- **Desktop only.** Deliberately — mobile browsers can't run this.

## Not implemented (v0.4)

MV3 extension, cross-machine sync, usage charts, editing the global settings (`dayStartHour`,
`idleSeconds`, …) from the GUI — the app manages the site list only, the rest are still file-level
values.

The Safari build has been installed and seen counting on a real Safari, but the first release
shipped with `@inject-into page`, which silently disabled all storage and config fetching (see the
setup note above). With that fixed, two assumptions are still unconfirmed and are steps 3 and 5 of
*Verifying the Safari install*: that Userscripts.app storage is genuinely shared across origins (the
whole per-site counter design rests on it), and whether the loopback settings server is reachable at
all under Safari's local-network policy. The script degrades to cached config if it isn't.
