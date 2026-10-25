# Scripts guide

Every command for this project, grouped by target. Referenced from [README.md](README.md).

## Chrome install

1. Install [Tampermonkey](https://www.tampermonkey.net/) in Chrome.
2. Open Tampermonkey → Dashboard → **+** (new script).
3. Paste the contents of `dist/webpage-time-tracker.user.js`. Save.
4. Open a tracked site. The badge appears immediately. It shows the used time and the limit for
   that site.

## Safari install

Safari needs the second build. Do not install the Chrome file in Safari.

1. Install [Userscripts](https://github.com/quoid/userscripts) from the App Store. It is free.
2. Enable it in Safari → Settings → Extensions.
3. Open the Userscripts toolbar popup. Create a new script.
4. Paste the contents of `dist/webpage-time-tracker.safari.user.js`. Save.
   You can also copy the file into the scripts directory that you selected in the extension
   settings. There is no fixed path. You select the location.
5. Open a tracked site.
6. Do the checks in [Verify the Safari install](#verify-the-safari-install). Two assumptions are
   specific to Safari. Confirm them one time.

The Safari build declares `@inject-into content`. Do not change that line. See
[README_AGENT.md — Safari inject-into content](README_AGENT.md#safari-inject-into-content).

Before you reinstall, delete the old script in Userscripts. An old copy with the same name hides
the new one.

## Verify the Safari install

1. **GM is live.** Open Safari → Settings → Advanced. Enable *Show features for web developers*.
   On a tracked site, open Develop → Show JavaScript Console. Reload the page. There must be no
   `[wtt] GM storage unavailable` warning.
2. **The counts persist.** Stay about 60 seconds on a tracked site. Keep the window focused and
   move the mouse. Note the badge. Reload the page. The badge must continue from about the same
   number. It must not show `0m`.
3. **The state is shared across origins.** Open a second tracked site. Then go back to the first
   site. The number of the first site must still be there. The per-site counter design needs this.
4. **The settings app runs.** Start it with `uv run wtt-config`. Keep the window open.
5. **The server is reachable.** Open `http://127.0.0.1:8787/config.json` in a Safari tab. Safari
   must show JSON. If macOS asks for *Local Network* access, allow it in System Settings →
   Privacy & Security → Local Network → Safari. If this step fails, the script is still correct.
   It stays on its cached config.
6. **The app drives the timer.** Keep a tracked tab open. Do not reload it. Change the limit of
   that site in the app and save. In 30 seconds the denominator on the badge must change. A count
   above the limit must show the overlay.
7. **A new site needs a reload.** This is by design. The host early-out already ran on that tab.

## Settings app

```sh
uv sync                    # create .venv, install the app and the dev tools
uv run wtt-config          # start the Tkinter settings window
uv sync --extra api        # add the anthropic SDK, for Suggest without the Claude CLI
```

The window lists the registered sites. Each row shows the favicon, the domain, the path and the
limit. The buttons are Add, Edit and Remove. A save writes `~/.webpage-time-tracker/config.json`
atomically.

The window also serves that file at `http://127.0.0.1:8787/config.json`. The server binds to
loopback only. The userscript reads it in the background, at most one time each 30 seconds across
all tabs, and caches the result in the userscript host storage. The app does not have to run. The
script uses the last config that it read.

Reload the tab after you change the settings. The open tab gets a new limit immediately. A site
that you just added needs a reload, because the host early-out already ran.

The **Suggest** button in the Add/Edit dialog proposes a host regex and a path regex for a domain.
An optional hint makes the proposal more narrow, for example "only Shorts". Suggest reads a small
built-in table first. On a miss it asks Claude through the Claude Code CLI (`claude`). Install the
CLI and log in first. If the CLI is not on `PATH` and `ANTHROPIC_API_KEY` is set, Suggest uses the
`anthropic` SDK instead. The app validates every suggestion. It caches the valid ones in
`~/.webpage-time-tracker/suggest-cache.json`.

## Development

Edit `src/`. Never edit `dist/`. The build script generates `dist/`, and a test compares `dist/`
with a fresh render of `src/`. A stale `dist/` fails the suite.

```sh
uv run python tools/build.py            # regenerate dist/ after any src/ change
uv run python tools/build.py --check    # verify dist/ is current, write nothing
uv run ruff check .                     # lint
uv run ruff format --check .            # formatting check
uv run mypy .                           # strict type check
uv run pytest                           # 160 tests
node --check dist/webpage-time-tracker.user.js          # syntax of the Chrome build
node --check dist/webpage-time-tracker.safari.user.js   # syntax of the Safari build
```

Set `WTT_HOME` to a temporary directory to keep a test or a manual run away from
`~/.webpage-time-tracker`. The tests do this in `tests/conftest.py`.

See also [README_AGENT.md — Build and dist](README_AGENT.md#build-and-dist) for the build contract,
and [SCHEMA.md](SCHEMA.md) for the config keys.
