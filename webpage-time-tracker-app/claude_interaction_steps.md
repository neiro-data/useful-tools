# Claude interaction log — webpage-time-tracker-app

Append-only. Terse entries: branch purpose + what was done.

---

## 2026-07-28 — `feat/webpage-time-tracker-userscript` (from `webpage-time-tracker`)

Greenfield. Scoped the idea (timer + nudge when over a threshold on time-sink pages) from scratch:
feasibility discussion first, no code until the design was settled.

- Ruled out Safari as first target — Safari Web Extensions need an Xcode app wrapper, signing resets
  on every restart without a paid Apple dev account, and `chrome.idle` is unsupported. Chrome first.
- Chose a Tampermonkey userscript over an MV3 extension for v0.1: no store, no signing, no build,
  and it validates the real question (do the nudges change behaviour?) cheaply.
- Decisions: single pooled budget across sites (not per-site), 45 min/day, daily reset at 04:00,
  rules = YouTube Shorts + Instagram Reels + X. Memes dropped.
- Built `webpage-time-tracker.user.js` (441 lines, no deps) + README.
- Notable: `GM_setValue` rather than `localStorage` for state, since `localStorage` is per-origin and
  can't pool a budget across origins. Shadow DOM for the overlay. `@match *://*/*` + host early-out
  so the rules list lives in one place.
- No specialist agents used — session config disallows spawning them unprompted; declared this
  rather than skipping the pipeline silently.
- Verified: `node --check` passes, no imports. Runtime behaviour needs manual testing in Chrome
  (can't drive Tampermonkey from here).

## 2026-07-28 — `feat/per-site-budgets-and-always-on-badge` (from `webpage-time-tracker`)

v0.2 PR 1 of 2. Pooled budget → per-site limits.

- State `wtt.state.v1` {day, seconds} → `wtt.state.v2` { days: { day: { site: seconds } } }, 14-day
  rolling history, pruned on read (ISO keys sort as dates). No migration — v1 held only today.
- `resync()` now merges per site, so two tabs on different tracked sites do not clobber each other.
- Each rule carries `limitMinutes` (Shorts 15, Reels 15, X 30); `budgetMinutes` deleted. Escalation
  ladder + snooze are per site.
- Badge always visible on a tracked page, dimmed under 50%; dropped the `at: 0.5` LEVELS entry since
  the badge no longer gates on a level.
- Menu: per-site status + 7-day trend; reset/grant act on the active site only.
- No specialist agents — session config disallows spawning them unprompted; declared, not skipped.
- Verified: `node --check` passes. Runtime needs manual Chrome testing.

## 2026-07-28 — `feat/config-gui-tkinter` (from `webpage-time-tracker`)

v0.2 PR 2 of 2. Site list moves out of the `.user.js` into a Tkinter app.

- New `uv` project rooted at the app folder: `config_gui/{models,store,icons,server,app}.py`,
  entry point `uv run wtt-config`. ruff (E,F,I,W,UP,S,B @ 100) + mypy strict + pytest, all clean.
- Config at `~/.webpage-time-tracker/config.json`; atomic save (`os.replace`). `WTT_HOME` env var
  overrides the directory so tests never touch the real one.
- `host`/`path` ship as regex source strings; the GUI builds them from a typed domain via
  `re.escape`, with an advanced toggle. Bad patterns rejected in Python, skipped (not thrown) in JS.
- Transport: `http.server` on 127.0.0.1:8787, GET /config.json only, daemon thread tied to the
  window. Userscript renders from its `wtt.config.v1` GM cache immediately and never blocks on the
  network; refresh rate-limited to once/60s across tabs. Live-applies to the current page; a newly
  added site needs a tab reload (the host early-out already ran).
- Icons: each site's own `/favicon.ico`, fetched once → PNG cache; drawn globe fallback (no binary
  asset in the repo, no third-party icon service). GUI-only, so host CSP is never involved.
- Deliberately not done: editing global settings in the GUI — site list only.
- No specialist agents — session config disallows spawning them unprompted; declared, not skipped.
- Verified: `node --check`, ruff, mypy, 36 pytest tests. GUI window + Tampermonkey behaviour need
  manual testing.

## 2026-07-28 — `fix/site-dialog-name-shadow-and-config-refresh` (from `webpage-time-tracker`)

Bug: per-site limits never updated. Two symptoms, one root cause + one gap.

- `SiteDialog` set `self._name = tk.StringVar(...)`, shadowing `tkinter.Misc._name`. `destroy()` then
  raised `TypeError: unhashable type: 'StringVar'`, so `_save()` blew up mid-callback: the dialog never
  closed, `wait_window` never returned a result, the edit was silently dropped, and closing the main
  window crashed on the stale child. Renamed all six Tk vars to `_var_*`; audited `App`/`SiteDialog`
  for other tkinter-internal collisions (none).
- `refreshConfig()` ran only once at startup, so an already-open tab never saw a changed limit. Added
  `setInterval(refreshConfig, CONFIG_REFRESH_MS)` after the host early-out; the cross-tab 60s rate
  limit is untouched. A newly added *host* still needs a reload (early-out already ran).
- `server.py` verified: `do_GET` re-reads via `store.load()` per request, no snapshot. No change.
- Agents: python-pro (fix) → test-automator (4 new regression tests in `tests/test_app.py`, verified
  failing against pre-fix code via stash) → code-reviewer (no material defects).
- Verified: ruff format/check, mypy strict, 40 pytest tests, `node --check`. GUI + Chrome behaviour
  still needs manual confirmation.

## feat/suggest-cli-auth — Suggest without an API key + dialog UX

- Suggest was unusable: `suggest_via_claude` demanded `ANTHROPIC_API_KEY`, which the user doesn't have
  and doesn't want to create. Now it shells out to the already-authenticated Claude Code CLI
  (`claude -p … --output-format json --model claude-haiku-4-5 --allowed-tools ""`, fixed argv, no
  shell). SDK path kept as fallback only when the CLI is unavailable *and* the key is set; `anthropic`
  moved to a `[project.optional-dependencies] api` extra.
- `_extract_json` added because the CLI wraps its answer in a ```json fence — confirmed against the
  real binary, the bare `json.loads` would have failed on every call.
- No second Suggest button: one call already returns both host and path, so the single button moved to
  the Domain row with an `(i)` hover tooltip naming the CLI requirement. Hint row relabelled
  "Suggest hint (optional)" + inline example; dead `_suggest_pending` removed.
- Agent: python-pro. Verified: ruff, mypy strict, 130 pytest tests, and a live `_claude_cli_text` call.
  Tk dialog layout still needs a manual look.
- Follow-up stages: test-automator (17 more tests — `_extract_json` cases, CLI envelope edges, cache-hit
  skips subprocess, CLI-wins-over-SDK precedence, plus first `_suggest_worker` coverage in test_app.py)
  → code-reviewer, which found one real defect: `subprocess.run` can raise OSError/PermissionError past
  the `SuggestUnavailable` contract, killing the worker thread with the button stuck on "Suggesting…".
  Fixed with an `except OSError` arm + regression test; also noted in-code that `--allowed-tools ""` is
  defense-in-depth, not a sandbox. 147 tests green.
