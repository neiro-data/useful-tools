# Schema

Every value this project keeps on disk or in userscript storage. Referenced from
[README.md](README.md).

The project has no database. It persists four things: one config file, one browser storage key for
the counters, one browser storage key for the cached config, and two caches in the application
directory.

## Application directory

`~/.webpage-time-tracker/`. Set the `WTT_HOME` environment variable to move it. The tests set it to
a temporary directory in `tests/conftest.py`.

| Path | Written by | Content |
| --- | --- | --- |
| `config.json` | `config_gui/store.py` | The settings, see below |
| `icons/<domain>.png` | `config_gui/icons.py` | One 20x20 PNG for each site favicon |
| `icons/_globe.png` | `config_gui/icons.py` | The drawn fallback icon |
| `suggest-cache.json` | `config_gui/regex_suggest.py` | Accepted regex suggestions, keyed by domain and hint |

The settings app writes `config.json` atomically. It writes a temporary file in the same directory,
then calls `os.replace`. A reader never sees a partial file.

## config.json

The settings app writes this file. The userscript reads it over loopback and caches it. The
`DEFAULTS` block in `src/core.js` is the fallback for a new install with no cache and no file.

| Key | Type | Default | Settings app accepts | Userscript accepts |
| --- | --- | --- | --- | --- |
| `version` | int | `1` | Written always | Ignored |
| `dayStartHour` | int | `4` | 0 to 23 | 0 to 23 |
| `idleSeconds` | int | `60` | 5 or more | 5 to 86400 |
| `snoozeMinutes` | int | `5` | 1 or more | 1 to 1440 |
| `historyDays` | int | `14` | 1 to 365 | 1 to 365 |
| `sites` | list | 3 entries | Each entry, see below | Each entry, bad ones dropped |

The day starts at 04:00 local time, not at midnight. A user cannot wait out the counter at 23:58.

### A site entry

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `name` | string | Yes | The label, and the key of the stored counter. Names must be unique |
| `host` | string | Yes | A regex source string, matched against `location.hostname` |
| `path` | string | No | A regex source string, matched against `location.pathname`. Omit it to track the whole site |
| `limitMinutes` | int | Yes | The daily limit for this site alone. 1 to 1440 |

The three default sites are:

| Name | `host` | `path` | `limitMinutes` |
| --- | --- | --- | --- |
| YouTube Shorts | `(^\|\.)youtube\.com$` | `^/shorts(/\|$)` | 15 |
| Instagram Reels | `(^\|\.)instagram\.com$` | `^/reels?(/\|$)` | 15 |
| X | `(^\|\.)(x\|twitter)\.com$` | none | 30 |

Type a plain domain in the settings app and it builds the `host` pattern. `youtube.com` becomes
`(^|\.)youtube\.com$`, which also covers the subdomains. An advanced toggle accepts a hand-written
regex instead.

### The name is the counter key

`name` keys the stored counter. Rename a site and its history starts again from zero. The settings
app refuses two sites with the same name, because they would share one bucket.

### The two validators are not identical

`config_gui/models.py` rejects a bad value and shows an error. `src/core.js` clamps a bad value to
the default and continues. The script must never fail at `document-start` because of one bad
number. The script also drops one site whose regex does not compile, and keeps the other sites.

`idleSeconds` and `snoozeMinutes` have no upper bound in the settings app, but the script clamps
them to 86400 and 1440. A larger number in the file works in the app and has no effect in the
browser.

## Userscript storage

The userscript host keeps these keys, not `localStorage`. `localStorage` is per origin, so it
cannot hold a counter that YouTube, Instagram and X all read.

| Key | Shape | Purpose |
| --- | --- | --- |
| `wtt.state.v2` | `{ days: { "YYYY-MM-DD": { "<site name>": seconds } } }` | The per-site daily totals |
| `wtt.config.v1` | The `config.json` object | The last config read from the settings app |
| `wtt.config.fetchedAt` | A timestamp in milliseconds | Rate-limits the config poll across all tabs |

The script prunes `wtt.state.v2` on each read. It keeps `historyDays` days, 14 by default. The
seconds are a float, because the tick adds a measured interval and not a constant.

The script writes the counter every 5 seconds, and it serializes all writes. See
[README_AGENT.md — Storage writes are serialized](README_AGENT.md#storage-writes-are-serialized).

## Last verified

2026-09-02, against `src/core.js`, `config_gui/models.py`, `config_gui/store.py` and
`config_gui/icons.py`. The suite collects 160 tests.
