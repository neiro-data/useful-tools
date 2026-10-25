# README for an agent

What you must know to change this repo, and what a user who only runs the tool does not need.
Referenced from [README.md](README.md).

## Source layout

`src/` holds five files. `dist/` holds two. Nothing else is a source of userscript code.

| File | Role |
| --- | --- |
| `src/header-chrome.js` | The `==UserScript==` metadata block for Tampermonkey |
| `src/header-safari.js` | The same block for Userscripts.app |
| `src/core.js` | All of the behaviour. It knows no platform API |
| `src/adapter-gm.js` | The Chrome adapter, over the synchronous `GM_*` functions |
| `src/adapter-safari.js` | The Safari adapter, over the promise-based `GM.*` functions |

`src/core.js` exposes `window.__wttMain`. Each adapter file builds an adapter object and calls it.
The core awaits every adapter method, so the Chrome adapter wraps its synchronous results in a
resolved promise.

## The adapter contract

A comment at `src/core.js:5` sends the reader to the README for this contract. This is the
contract. An adapter must supply four methods.

| Method | Returns | Rule |
| --- | --- | --- |
| `getValue(key, fallback)` | A promise for the value | Return `fallback` on any failure. Never throw |
| `setValue(key, value)` | A promise | Swallow a storage failure. Never throw |
| `fetchConfig(url, timeoutMs)` | A promise for the body text, or `null` | `null` means "the cache stands" |
| `registerMenu(items)` | Nothing | Optional extra surface. The core already draws its own menu |

The core draws the badge menu into a closed shadow root on every platform. `registerMenu` is a
bonus, not a requirement. On Chrome it adds the three commands to the Tampermonkey icon menu. On
Safari it does nothing, because Userscripts.app has no equivalent API.

## Build and dist

`dist/` is generated. Never edit it by hand.

`tools/build.py` is the only producer. It is stdlib-only, and it concatenates three source files
with one blank line between them. There is no template and no bundler, so byte equality is a valid
test.

```sh
uv run python tools/build.py            # write both dist files
uv run python tools/build.py --check    # compare only, exit 1 if stale
```

`tests/test_dist_freshness.py` re-renders both targets and asserts byte equality with the committed
files. An edit in `src/` without a build run fails the suite. Run the build and commit `dist/` in
the same change.

The two builds differ only in the header and the adapter. `src/core.js` is byte-identical in both.

## Safari inject-into content

`src/header-safari.js` declares `@inject-into content`. This line is load-bearing.

Userscripts.app exposes the `GM.*` APIs to the content world only. With `@inject-into page` every
`GM.*` call throws, the adapter swallows the error, and the script runs on its baked-in `DEFAULTS`.
The badge counts, nothing persists across a reload, and the settings app is never contacted. The
first Safari release shipped this way.

`src/adapter-safari.js` now logs `[wtt] GM storage unavailable` one time if the condition returns.
Check the console for that string before you trust a Safari install.

The cost of `content` is that the `history.pushState` patch no longer sees the navigations of the
page. The 1-second tick re-derives the active rule from `location.pathname`, so SPA routing still
works.

The Safari header also omits `@connect`, because Safari has no equivalent. If the local-network
policy blocks the loopback server, the script keeps its cached config and backs off the poll.

## Storage writes are serialized

`src/core.js` chains every storage mutation onto one promise (`ioChain`). Do not replace this with
a boolean mutex.

The Safari storage API is asynchronous. A boolean mutex drops a `resync()` call that arrives while
a write is in flight, and a dropped resync is the one that matters: a tab becomes active after
another tab advanced the counter. The chain queues instead of dropping.

One consequence stands: a write in flight when the tab unloads may not land. The cost is at most
about 6 seconds of counted time.

## SPA routing

`youtube.com/shorts/...` fires no page load. The core patches `history.pushState` and
`history.replaceState`, and it listens to `popstate`.

The 1-second tick is the backstop if the patch does not take in the sandbox of the host. Keep both.

The `@match` value is `*://*/*` on purpose, so the site list lives in the config alone. A hostname
that matches no rule returns immediately and costs the page nothing. The hostname cannot change
without a page load, so the early-out is safe. The path can change, so path matching stays dynamic.
This is also why a newly added site needs a tab reload: the early-out already ran on that tab.

## The config poll

`CONFIG_REFRESH_MS` is 30000 in `src/core.js`. The poll is rate-limited across all tabs through the
`wtt.config.fetchedAt` key.

An unreachable loopback server is the normal state, because the settings app is open only
sometimes. The delay doubles after each consecutive failure, up to `MAX_CONFIG_POLL_MS`, which is
10 minutes. A success resets it to 30 seconds.

Only a tracked page installs the recurring poll. A page that takes the host early-out warms the
cache one time and schedules nothing.

## Versions do not match, and that is expected

| Where | Value |
| --- | --- |
| `src/header-chrome.js:4` and `src/header-safari.js:4` | `0.3.0`, the userscript version |
| `pyproject.toml:3` | `0.2.0`, the settings app version |

The two ship together and version independently. Bump the header version when `src/` changes, and
run the build.

## Unconfirmed assumptions

The Safari build runs and counts on a real Safari. Two assumptions are still unconfirmed. They are
steps 3 and 5 of
[scripts-guide.md — Verify the Safari install](scripts-guide.md#verify-the-safari-install).

1. Userscripts.app storage is shared across origins. The whole per-site counter design needs this.
2. The loopback settings server is reachable under the local-network policy of Safari. If it is
   not, the script stays on its cached config.

## Not implemented

- An MV3 extension.
- Sync between machines.
- Usage charts.
- Editing the global settings from the settings app. The app manages the site list only.
  `dayStartHour`, `idleSeconds`, `snoozeMinutes` and `historyDays` stay file-level values.

## Docs map

| File | For | Content |
| --- | --- | --- |
| [README.md](README.md) | A user | What the tool is, one first run, the behaviour, the layout |
| [scripts-guide.md](scripts-guide.md) | A user or a developer | Every command, grouped by target |
| [SCHEMA.md](SCHEMA.md) | Either | `config.json`, the storage keys, the files on disk |
| README_AGENT.md | An agent | This file. Contracts, drift warnings, open questions |
