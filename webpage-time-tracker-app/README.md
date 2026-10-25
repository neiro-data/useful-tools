# Webpage Time Tracker

## Resume

A personal userscript that measures the time you spend on time-sink websites. Each site has its own
daily limit. The script shows a badge with the time used, and it escalates the nudges when you go
past the limit.

- **Stack:** plain JavaScript, no dependencies and no bundler. A shared core and one adapter for
  each platform live in `src/`. A stdlib-only Python script, `tools/build.py`, concatenates them
  into the two installable userscripts in `dist/`.
- **Second part:** an optional settings app in Python, with `uv` and Tkinter, in `config_gui/`. It
  manages the site list.
- **Entry points:** `dist/webpage-time-tracker.user.js` for Chrome,
  `dist/webpage-time-tracker.safari.user.js` for Safari, and `uv run wtt-config` for the settings
  app.
- **Host requirements:** Chrome with Tampermonkey, or Safari with Userscripts.app. Python 3.11 or
  later and `uv` for the settings app. Desktop only. Personal use, not published to a store.
- **History:** the script keeps 14 days of per-site totals. Nothing acts on the history.

## Agent read

If you are an AI agent, read also [README_AGENT.md](README_AGENT.md).

## Quick start

The counter works without the settings app. Start with the userscript alone.

1. Install [Tampermonkey](https://www.tampermonkey.net/) in Chrome.
2. Open Tampermonkey → Dashboard → **+**, and paste `dist/webpage-time-tracker.user.js`. Save.
3. Open `youtube.com/shorts`. A badge appears at the bottom right: `YouTube Shorts · 0:00 / 15:00`.

To change the site list, run the settings app. Add or edit a site, save, then reload the tracked
tab.

```sh
uv sync                    # create .venv and install, one time
uv run wtt-config          # the Tkinter settings window
```

Safari needs the second build and one verification pass. See
[scripts-guide.md — Safari install](scripts-guide.md#safari-install). Every other command is in
[scripts-guide.md](scripts-guide.md).

## How time is counted

Open-tab time is not useful, because a background tab collects hours. One second counts only when
all four conditions are true.

- The tab is visible.
- The window of the browser has the focus. Another application with the focus stops the clock.
- Input occurred in the last `idleSeconds`.
- The URL matches a rule.

Only one tab is visible and focused at a time, so two tracked tabs cannot count twice. The script
measures the elapsed time from real timestamps, and it limits one step to twice the tick. A closed
laptop adds no hours of use.

## Escalation ladder

The ratio is the time used on this site divided by the limit of this site. Each site climbs its own
ladder. A site over its limit does not change the behaviour of another site.

| Ratio | Behaviour |
| --- | --- |
| Below 50% | Badge at the bottom right, dimmed |
| 50% or more | Badge at full opacity |
| 100% or more | Badge turns red, and a full-screen overlay appears. Dismiss is immediate |
| 125% or more | Overlay, and Dismiss becomes active after 5 seconds |
| 150% or more | Overlay, the page turns grayscale, and each `<video>` element pauses |

Dismiss hides the overlay for `snoozeMinutes`, 5 by default. The snooze applies to one site. The
badge stays visible during the snooze.

## Menu

Click the badge on a tracked site. The script draws the menu inside its own closed shadow root, so
it behaves the same on both browsers.

- **status** — the used time and the limit of each site today, and a 7-day trend for all sites.
- **reset this site's counter** — sets the current site back to zero.
- **grant 10 more minutes here** — a deliberate override for the current site.

Chrome also registers the same three commands in the Tampermonkey icon menu. Userscripts.app has no
equivalent API, and this is the reason the badge menu exists.

## Schema

The settings app writes `~/.webpage-time-tracker/config.json`. The userscript reads that file over
loopback, at `http://127.0.0.1:8787/config.json`, and caches it. The settings app does not have to
run: the script uses the last config it read.

The file holds four global values and a list of sites. Each site has a name, a host regex, an
optional path regex and its own limit in minutes. The counters live in userscript storage, not in
`localStorage`, because every tracked origin must read them.

Read [SCHEMA.md](SCHEMA.md) for every key, every default, the accepted ranges and the storage keys.

## Notes and limits

- **This is a speed bump, not a lock.** A user disables the userscript host in two clicks.
- **Desktop only.** A mobile browser cannot run this.
- **A new site needs a tab reload.** An open tab picks up a new limit on its own, in 30 seconds. A
  site you just added was already ruled out at page load.
- **A rename resets the history of that site.** The name is the key of the stored counter.

## Layout

```
webpage-time-tracker-app/
├── src/                  5 source files: 2 headers, the core, 2 adapters
├── dist/                 2 generated userscripts — built by tools/build.py, never edit
├── tools/build.py        the stdlib-only build script
├── config_gui/           the Tkinter settings app (app, models, store, server, icons, suggest)
├── tests/                8 test modules, 160 tests
├── pyproject.toml        the settings app package, the ruff and mypy configuration
├── README.md             this file
├── scripts-guide.md      every command, grouped by target
├── SCHEMA.md             config.json, the storage keys, the files on disk
└── README_AGENT.md       contracts, drift warnings, open questions
```
