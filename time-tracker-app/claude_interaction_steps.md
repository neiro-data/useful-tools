# Claude Interaction Steps

This file logs Claude Code interactions (one entry per feature branch/task) for this repo.

## Phase 0 — scaffold

**Branch/task:** initial project scaffold.

**Summary:** Initialized a `uv`-managed FastAPI project for a personal, offline-first time
tracker (FastAPI + SQLite backend, React SPA frontend to follow in a later phase).

**Steps taken:**
- Initialized the project with `uv init` (Python 3.11+ target), producing `pyproject.toml` and
  `uv.lock`.
- Added runtime dependencies: `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`,
  `python-dateutil`.
- Added dev dependencies: `ruff`, `mypy`, `pytest`, `httpx`.
- Configured tooling in `pyproject.toml`: `ruff` (line-length 100, double quotes, 4-space
  indent, lint rules `E,F,I,W,UP,S,B`), `mypy` (strict), `pytest`.
- Created the base app structure:
  - `app/main.py` — FastAPI app with `GET /health`, CORS enabled for localhost dev origins, and
    a root router include stub.
  - `app/config.py` — `pydantic-settings` `Settings` (env-driven, prefix `TIME_TRACKER_`).
  - `app/api.py` — empty root `APIRouter` stub for future feature routers.
  - `app/db.py` — minimal SQLite connection helper; schema/migrations intentionally left as a
    `TODO` for a later phase/agent.
  - `tests/test_health.py` — `TestClient`-based test for `/health`.
- Added `.gitignore`, `README.md`.
- Verified: `uv sync`, `uv run ruff check .`, `uv run pytest -q`, and a clean import of
  `app.main` all pass.

**Agent:** backend-developer (scaffold only — no business logic or DB schema).

## Phase 0 — schema

**Branch/task:** 6-table SQLite schema + idempotent init + indexes + tests (sql-pro).

**Summary:** Implemented the normalized SQLite schema (`entries`, `categories`, `tags`,
`entry_tags`, `report_exports`, `settings`) and an idempotent migration/bootstrap module wired
into the FastAPI app.

**Steps taken:**
- Added `app/schema.py`: DDL for all 6 tables (`IF NOT EXISTS`), enum-like columns constrained
  via `CHECK`, ISO-8601 UTC TEXT timestamps, FK cascades on `entry_tags` (`ON DELETE CASCADE`) and
  `entries.category_id` (`ON DELETE SET NULL`).
- Added 3 targeted indexes: `idx_entries_start_ts` (date-range report/dashboard scans),
  `idx_entries_category_id` (category filtering), `idx_entry_tags_tag_id` (reverse tag lookups;
  the PK on `entry_tags` already covers the entry_id direction).
- `init_db(conn)` creates schema then seeds a single default `settings` row if none exists;
  exposed as `create_schema()`/`init_db()`, runnable standalone via `uv run python -m app.schema`.
- Wired `init_db` into `app/main.py` via a FastAPI `lifespan` context manager (startup hook).
- Added `tests/test_schema.py`: asserts all 6 tables + 3 indexes exist, FK enforcement (bad
  `entry_tags` insert raises `IntegrityError`), `CHECK` constraint enforcement, idempotent
  re-init, and the default `settings` row seeding.
- Verified: `uv run ruff check .`, `uv run mypy app`, `uv run pytest -q` all pass (8 tests).

**Agent:** sql-pro.

## Phase 1 — API contract

Phase 1 — API contract: schemas + endpoint spec for categories/tags/entries/timer (api-designer).

**Branch/task:** design (not implement) the REST contract for Phase 1 core capture — categories,
tags, entries (manual mode), timer (single-active-timer rule), and a Today convenience
aggregation. Reports/exports are Phase 2, out of scope.

**Steps taken:**
- Added `app/schemas.py`: pydantic v2 request/response models (`CategoryCreate/Update/Read`,
  `TagCreate/Update/Read`, `EntryCreateManual`, `EntryUpdate`, `EntryRead`, list-response
  envelopes, `TimerStartRequest`/`TimerStopRequest`/`TimerCurrentResponse`, `TodayResponse`,
  `ErrorResponse`/`ErrorDetail`), with validators (`end_ts >= start_ts`, non-empty titles/names)
  and `json_schema_extra` examples.
- Added `app/API_CONTRACT.md`: full endpoint table (method/path/purpose/body/response/status
  codes), a shared error envelope with a `code` catalog, pagination/partial-update/soft-delete
  conventions, and explicit rules for the single-active-timer conflict (`409
  timer_already_running` / `409 no_running_timer`) and duration computation
  (`duration_minutes` always server-computed from `start_ts`/`end_ts`, never trusted from the
  client).
- Added `app/routers/{categories,tags,entries,timer,today}.py`: resource routers with full
  signatures, `response_model`s, and docstrings, bodies stubbed as `raise NotImplementedError` for
  the backend-developer to fill in; added `app/deps.py` (`get_db`/`DbDep`) as the shared DB
  dependency. Wired all routers into `app/api.py`'s root router.
- Verified: `uv run ruff check .`, `uv run mypy app` (strict), `uv run pytest -q` (8 tests, incl.
  `/health`) all pass; confirmed all 12 new routes register and the OpenAPI schema builds via
  `app.main.app.openapi()`.

**Agent:** api-designer (design/spec only — no route logic implemented).

## Phase 1 — design system + Today/Week wireframes

Phase 1 — design system + Today/Week wireframes (ui-designer).

**Branch/task:** design (not implement) the visual/interaction design system and the Today + Week
screen layouts for the React SPA frontend (to be built in a later phase).

**Steps taken:**
- Added `design/DESIGN_SYSTEM.md`: principles, 8px spacing scale, typography scale (system font
  stack + monospace for durations/timestamps), layout grid/breakpoints, a 12-hue fixed category
  color palette (WCAG AA-verified ≥4.5:1 in both light and dark themes), and component patterns
  (buttons, inputs, entry row, timer widget, category/tag chips, totals bar/segmented breakdown).
- Added `design/tokens.css`: framework-agnostic CSS custom properties (spacing, radius, typography,
  motion, shadows, semantic colors, 12 category color tokens) with a light default theme and a
  `prefers-color-scheme: dark` override block.
- Added `design/screens.md`: annotated wireframes for Today (quick-add, live timer, recent
  category/tag rail, entries list) and Week (week nav, totals summary, by-category/by-tag
  breakdown, collapsible day groups), covering empty/loading/active-timer/conflict states and
  keyboard shortcuts for fast entry.
- Verified all 12 category colors against `--color-bg`/`--color-surface` in both themes via a
  WCAG relative-luminance contrast check (all pass ≥4.5:1; light theme 4.81–6.77, dark theme
  5.85–11.07).

**Agent:** ui-designer (design/spec only — no React code implemented).

## Phase 1 — API implementation

Phase 1 — API implementation: entries/timer/categories/tags routes + 54 tests (backend-developer).

## Phase 1 — frontend

Phase 1 — frontend: React Today + Week screens, typed API client, design tokens (frontend-developer).

**Branch/task:** build the React SPA frontend (Today, Week, and — added mid-task — Month screens)
against `app/API_CONTRACT.md`/`app/schemas.py` and the `design/` design system.

**Steps taken:**
- Scaffolded `frontend/` with Vite + React 19 + TypeScript (strict: `strict`, `noImplicitAny`,
  `strictNullChecks`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`), `react-router-dom`
  for routing, ESLint (flat config, `typescript-eslint` + `eslint-plugin-react-hooks` +
  `eslint-plugin-react-refresh` + `eslint-config-prettier`), Prettier, and Vitest +
  `@testing-library/react` for component tests.
- Added a typed API client (`src/api/`): `client.ts` (fetch wrapper), `errors.ts` (`ApiError` with
  `isTimerAlreadyRunning`/`runningEntryId` helpers), `types.ts` (mirrors `app/schemas.py`), and one
  module per resource (`categories`, `tags`, `entries`, `timer`, `today`). All non-2xx responses are
  normalized into `ApiError` carrying the backend's `code`/`message`/`details`.
- Configured a Vite dev proxy (`/api/*` → `http://127.0.0.1:8000`, overridable via
  `VITE_BACKEND_ORIGIN`) so the app calls same-origin relative paths with no CORS setup.
- Imported `design/tokens.css` globally in `main.tsx`; all components consume `var(--...)` tokens
  (category colors via `--cat-*`, never hardcoded hex).
- Built shared components: `EntryRow` (view + inline edit + delete-confirm), `CategoryChip`,
  `TagChip`/`TagEditor`, `CategoryPicker`, `TimerWidget` (idle quick-add vs running timer, one
  component per §8.4), `RecentChipsRail` (number-key shortcuts 1–6 / Shift+1–6), `ManualEntryForm`,
  `DayGroup` (collapsible per-day section + "+ Add entry"), `SegmentedBreakdown` (category/tag
  breakdown + legend, reused by Week and Month), `MiniBarChart`, `TimerBanner` (sticky
  running-timer banner), `AppShell` (nav rail with Today/Week/Month live, Reports/Settings
  disabled placeholders), `Skeleton`.
- Built `TodayPage`, `WeekPage`, and `MonthPage`. Month was added as a mid-task scope addition: it
  reuses Week's `DayGroup`/`SegmentedBreakdown`/`EntryRow` components verbatim over a
  calendar-month range instead of a week, fetching `GET /entries` with a month-range date filter
  and aggregating client-side (`utils/aggregate.ts`, `hooks/usePeriodEntries.ts` — both shared with
  Week); no backend changes were needed.
- Implemented the `409 timer_already_running` conflict as an inline banner on Today ("Stop it and
  start this instead" / "Cancel"), per `design/screens.md` §1.5.
- Added Vitest + Testing Library coverage for `EntryRow` (view/edit/delete states, running-entry
  duration display) and `TimerWidget` (idle form validation/start, running-state rendering).
- Verified: `npm run lint`, `npm run test` (7 tests passing), and `npm run build` (tsc -b + vite
  build) all green.

**Agent:** frontend-developer.

Phase 1 — test hardening: e2e backend lifecycle + edge cases, frontend error-envelope + aggregation tests (test-automator).

Phase 1 — review fixes: generic 500 envelope handler + documented DELETE-cancels-running-timer, with tests (backend-developer).

---

## Phase 2 — Task 1: Reports API + timezone-consistent day boundaries

**Branch:** `feat/reports-api` (PR flow — branch → PR → human review; no direct-to-main).

- Added a shared tz-aware day-boundary helper in `app/repo.py` (`get_settings_timezone`,
  `local_day_bounds_utc`, `local_range_bounds_utc`), reusing the `combine(time.min/max, tz)
  .astimezone(UTC)` pattern from `today.py`.
- Refactored `app/routers/today.py` to use the helper (no behavior change) and fixed the latent
  day-boundary bug in `app/routers/entries.py` `list_entries`: `start_date`/`end_date` filters now
  honor `settings.timezone` instead of hardcoded `+00:00` UTC-midnight strings.
- New `GET /reports/summary?period={week|month|quarter}&date=YYYY-MM-DD` endpoint
  (`app/routers/reports.py`, registered in `app/api.py`) returning tz-aware period totals with
  `by_category`, `by_tag` (intentional multi-tag double-count, documented), and `by_day`
  (only days with entries). New `Report*` pydantic models + `ReportPeriod` enum in `app/schemas.py`.
  Only completed entries counted; running timer excluded. `API_CONTRACT.md` updated.
- Tests: `tests/test_reports.py` — 10 new tests incl. a UTC↔Asia/Tokyo day-boundary regression test
  proving both `/entries` and `/reports/summary` honor the local-day boundary. Suite: 70 passing.
- Verified: `ruff format`/`ruff check`/`mypy app` clean; full `pytest` green (70).
- Code review: no blocking issues. Non-blocking follow-ups noted (redundant `local_range_bounds_utc`
  call in entries.py; N+1 tag lookup in reports.py) — deferred.

**Agents:** backend-developer (impl), test-automator (tests), code-reviewer (review). All edits on Sonnet.

## Phase 2 — Task 2: Settings API (GET/PATCH singleton settings)

**Branch:** `feat/settings-api` (PR flow — branch → PR → human review; no direct-to-main).

- New `app/routers/settings.py` (registered in `app/api.py`): `GET /settings` returns the singleton
  settings row; `PATCH /settings` partially updates it (`exclude_unset`, empty body = no-op).
  The row is treated as a singleton — PATCH only ever `UPDATE`s the single row (never insert/delete),
  and builds a parameterized dynamic `UPDATE` restricted to a fixed `_MUTABLE_COLUMNS` allowlist
  (column names never from user input; values always `?`-bound), inside `transaction(db)` (BEGIN
  IMMEDIATE) matching `entries.update_entry`.
- `app/schemas.py`: added `SettingsRead` / `SettingsUpdate` models + new `WeekStart`
  (`monday`/`sunday`) and `ExportFormat` (`html`/`csv`/`pdf`/`md`) str enums whose values match the
  DB `CHECK` constraints exactly; reused `EntryMode` for `default_entry_mode`. `database_label`
  strip-and-reject-blank via field validator.
- Validation: `timezone` must be a valid IANA zone (checked via `zoneinfo.ZoneInfo`, raising the
  app's `ValidationError` → 422 envelope) — critical since timezone drives day-boundary math.
- `app/repo.py`: added `settings_from_row(row) -> SettingsRead` helper. `API_CONTRACT.md`: new
  `## Settings` section documenting both endpoints, singleton semantics, and the IANA-tz rule.
- Tests: `tests/test_settings.py` — 11 new (GET defaults, single/multi-field PATCH, empty-body
  no-op, invalid-timezone/blank-label/enum 422s, singleton invariant across patches, tz round-trip).
  Suite: 81 passing (70 + 11).
- Verified: `ruff format`/`ruff check`/`mypy app` clean; full `pytest` green (81).
- Code review: no blocking issues. Non-blocking notes: `week_starts_on` lacks a DB CHECK (app-level
  enum is sole write path); `_get_settings_row` assert is an intentional non-user-facing invariant
  guard. Deferred.

**Agents:** backend-developer (impl), test-automator (tests), code-reviewer (review). All edits on Sonnet.

## Phase 2 — Task 3: Exports API (SQLite backup + CSV + Outlook-friendly HTML)

**Branch:** `feat/exports` (PR flow — branch → PR → human review; no direct-to-main).

- New `app/routers/exports.py` (registered in `app/api.py`) with three download endpoints:
  - `GET /exports/backup` — full DB snapshot via SQLite's **online backup API**
    (`db.backup(dest)`) into a `tempfile.NamedTemporaryFile`, served as an
    `application/octet-stream` attachment and unlinked afterward via a `BackgroundTask` (consistent
    even under concurrent writes; no premature delete, no leak).
  - `GET /exports/entries.csv` — completed entries as a `text/csv` attachment; optional
    `start_date`/`end_date` (inclusive, timezone-aware, reusing `get_settings_timezone` +
    `local_range_bounds_utc` exactly like `entries.list_entries`; `end_date < start_date` → 422).
    Columns: `id,title,category,start_ts,end_ts,duration_minutes,entry_mode,tags,notes`
    (raw stored UTC ISO timestamps; tag names `; `-joined). Running timer excluded.
  - `GET /exports/report.html` — inline `text/html` (not an attachment); `period` (required) +
    optional `date`. **Reuses `reports.get_reports_summary`** (zero duplicated aggregation) and
    renders it as self-contained, inline-styled, `<table>`-based Outlook-pasteable HTML with all
    user strings `html.escape`d.
- Filenames use a `_safe_filename_slug(database_label)` helper (strips to `[a-z0-9-]` → no
  `Content-Disposition` header injection / path traversal).
- `API_CONTRACT.md`: new `## Exports` section documenting all three endpoints.
- Tests: `tests/test_exports.py` — 12 new (backup octet-stream + valid SQLite magic header; CSV
  header/rows, category+tags, running-timer exclusion, date-range filter, 422 path; HTML inline,
  period range + category present, self-contained, period required). Suite: 93 passing (81 + 12).
- Verified: `ruff format`/`ruff check`/`mypy app` clean; full `pytest` green (93).
- Code review: no blocking issues. Non-blocking notes: consider CSV formula-injection guard
  (prefix `=`/`+`/`-`/`@` when opened in Excel); CSV date-filter block mildly duplicates
  `entries.list_entries` logic. Deferred.

**Agents:** backend-developer (impl), test-automator (tests), code-reviewer (review). All edits on Sonnet.

## Phase 2 — Task 4: Rule-based weekly narrative summary

**Branch:** `feat/weekly-narrative` (PR flow — branch → PR → human review; no direct-to-main).

- New `GET /reports/narrative` endpoint (added to the existing `reports.router`, no new router
  file / no `app/api.py` change). Rule-based, **no LLM / no external calls** — pure-Python string
  assembly over the report aggregation.
- **Reuses `reports.get_reports_summary(db, period, date)` directly** (zero duplicated
  SQL/date/timezone math); same `period` (week/month/quarter, required) + optional `date`
  (defaults to today in `settings.timezone`) contract as `/reports/summary`.
- New `ReportNarrativeResponse` schema (`app/schemas.py`): `period`, `start_date`, `end_date`,
  `timezone`, `narrative: str`, `highlights: list[str]`.
- `_build_narrative()` rule engine composes an ordered `highlights` list + prose `narrative` from:
  total time + entry count, top category (name/"Uncategorized" + time + whole-percent share) and
  second category, busiest day (weekday name + date + time), daily average across **days-with-
  entries** (not calendar days), and top tag (phrased neutrally re: tag double-counting). Empty
  period (`entry_count == 0`) short-circuits to a single "no time tracked" highlight — guards
  div-by-zero / empty-list.
- DRY: promoted the `Hh Mm` minutes formatter to a shared `format_minutes()` in `reports.py`;
  `exports.py` now imports it (dropped its duplicate `_format_minutes`; no new import cycle —
  `exports.py` already imported from `reports.py`).
- `API_CONTRACT.md`: new narrative subsection (params, response shape, composition order,
  active-day denominator, empty-period behavior).
- Tests: `tests/test_narrative.py` — 4 new (empty-period highlight/shape; seeded 2-category/1-tag
  week asserting top category + share, busiest weekday, daily average, top tag, ordered non-empty
  highlights; `period` required → 422; reconciliation of narrative figures vs `/reports/summary`).
  Suite: 97 passing (93 + 4).
- Verified: `ruff check`/`ruff format`/`mypy app` clean (19 source files); full `pytest` green (97).
- Code review: no blocking issues. Non-blocking: `_build_narrative` recomputes top-share /
  busiest-day / daily-average once for `highlights` and again for the prose string — a DRY
  opportunity (build highlights first, reuse). Deferred.

**Agents:** python-pro (impl), test-automator (tests), code-reviewer (review). All edits on Sonnet.

## Post-Phase-2 cleanup — T1: CSV formula-injection guard (SECURITY)

**Branch:** `fix/csv-formula-injection` (PR flow — branch → PR → human review; no direct-to-main).

- **Why:** `GET /exports/entries.csv` wrote user-controlled string fields unescaped; a cell value
  starting with `= + - @` (or tab/CR) can execute as a formula when the CSV is opened in
  Excel/Sheets (OWASP CSV injection). Flagged as a non-blocking note during the Task 3 export review.
- **Fix (`app/routers/exports.py`):** added module-level `_CSV_FORMULA_PREFIXES = ("=","+","-","@","\t","\r")`
  and a `_csv_safe(value)` helper that prefixes at-risk strings with a single quote `'`; non-string
  values and empty strings pass through unchanged. Applied to the four user-supplied columns
  (`title`, `category`, `tags`, `notes`); system-generated columns (`id`, `start_ts`, `end_ts`,
  `duration_minutes`, `entry_mode`) left untouched. Header row unaffected.
- **Test (`tests/test_exports.py`):** `test_export_entries_csv_neutralizes_formula_injection` —
  seeds a tag/entry titled `=cmd()|'/C calc'!A0` + notes `=SUM(A1:A9)`, hits the endpoint, parses
  the CSV, and asserts title/tags/notes come back `'`-prefixed while `duration_minutes` is unchanged.
- Verified: `ruff check .` clean, `mypy app` clean (19 files), full `pytest` green (98 = 97 + 1).

**Agents:** python-pro (impl + test). All edits on Sonnet.

## Post-Phase-2 cleanup — T2: DRY refactor of `_build_narrative` (reports.py)

**Branch:** `refactor/narrative-builder` (PR flow — branch → PR → human review; no direct-to-main).

- **Why:** `_build_narrative` (`app/routers/reports.py`) computed its derived values twice — once
  for the ordered `highlights` list and again for the prose `narrative` string. Flagged as a
  non-blocking DRY note during the Task 4 narrative review.
- **What:** compute each derived value once (top-category name + `top_share`, second-category name,
  busiest-day `weekday_name`, `daily_average_minutes`) in the highlights block; the narrative block
  now reuses those locals instead of recomputing the `Uncategorized` fallback / share math /
  `strftime` / average division. Pre-initialized to `""`/`0` before the guarded blocks (never read
  when the same `if` guard is false, so output is unchanged). Structure, ordering, guards, and the
  `else: narrative += "."` punctuation branch are untouched.
- **Byte-identical output** was the hard constraint — pure de-duplication, no wording change.
- Verified: `ruff check .` clean, `mypy app` clean (19 files), full `pytest` green (98). Narrative
  tests (`tests/test_narrative.py`) still pass unchanged, confirming identical prose.

**Agents:** python-pro (impl). All edits on Sonnet.

## Post-Phase-2 cleanup — T3+T4+T5 batched (frontend)

**Branch:** `frontend/reports-settings-cleanup` (PR flow — branch → PR → human review; no direct-to-main).
Three non-overlapping frontend cleanups batched into one PR (plan allowed batching the frontend tasks).

### T3 — hook `cancelled`-guard in `reload()` (correctness)
- **Why:** in `useReportSummary`/`useSettings`/`usePeriodEntries`, the effect's `cancelled` flag only
  guarded `setError`/`setLoading` — NOT the `setState` calls inside `reload()`. A `reload()` resolving
  after unmount wrote state on an unmounted component.
- **Fix:** replaced the per-effect `cancelled` local with a shared `mountedRef` (`useRef(true)`) in all
  three hooks; `reload()` checks `mountedRef.current` before each setState. Ref is set `true` at effect
  entry (so dep-change re-subscribe re-arms it) and `false` in cleanup. Public `reload(): Promise<void>`
  signature unchanged. Consistent across all three hooks.
- **Tests:** unmount-before-resolve test added to `useReportSummary.test.ts`, `useSettings.test.ts`, and a
  new `usePeriodEntries.test.ts` — assert no state write / act warning after unmount.
- **Known residual (non-blocking):** the shared ref can't distinguish "unmounted" from "superseded by a
  newer period/date", so a rapid dep-switch could still write stale *data*. That race pre-existed (the old
  `reload` had no guard at all); this is strictly an improvement. A request-token/AbortController per
  effect would fully close it — deferred.

### T4 — a11y polish
- Settings: gave the (validation) hint `<p>`s stable ids + wired `aria-describedby` on the matching input
  (conditional, only when the hint renders). Reports: added `aria-label="Reset date to today"` to the date
  anchor's "Today" reset button. `MiniBarChart`: for ranges > 7 days, labels switch from repeating weekday
  names to date labels (`formatShortDate`, e.g. "Jul 3") and are thinned (~8 evenly spaced, last always
  shown); ≤7-day Week behavior visually unchanged. Added `formatShortDate` to `utils/dateRange.ts`.

### T5 — extract `API_PREFIX` constant
- `export`ed the existing `API_PREFIX = "/api"` from `api/client.ts`; `api/reports.ts`'s three export-URL
  builders now use it instead of a hardcoded `/api`. Runtime URLs byte-identical. Updated `reports.test.ts`'s
  `vi.mock("./client", …)` factory to also expose `API_PREFIX` (mock previously only stubbed `apiRequest`).

- Verified (in `frontend/`): `npm run lint` clean, `npx tsc --noEmit` clean, `npx vitest run` green
  (51 tests, 11 files).

**Agents:** react-specialist (T3), frontend-developer (T4+T5). All edits on Sonnet.

## Branch `seed-categories-file` — declarative category seeding from TOML

**Goal:** replace Step 1 of `How-to-guide.md` (create categories via `curl -X POST /categories`) with a
version-controlled file in the repo, so the category taxonomy is reproducible on a fresh database.

**Format decision:** TOML at `seed/categories.toml`. Chosen over JSON (no comments — and this is a
hand-curated taxonomy that benefits from inline rationale) and YAML (would add a `pyyaml` dependency for
one file). `tomllib` is stdlib on the project's `requires-python = ">=3.11"` floor, and TOML is already the
repo's config language.

**Sync semantics decision:** full-sync upsert, keyed on `categories.name` (already UNIQUE in
`app/schema.py`). Rows in the file but not the DB are inserted; rows already present have `color`/
`sort_order` updated to match the file. Nothing is ever deleted, so categories with entries attached can't
be orphaned and UI-created categories survive a run.

**Two deliberate design calls:**
- `is_active` is NOT synced. Deactivation stays UI-owned — syncing it would resurrect a category the user
  explicitly retired via `POST /categories/{id}/deactivate` on the next run.
- NOT wired into `init_db` (unlike `_seed_default_settings`). Because the sync overwrites `color`/
  `sort_order`, running it at startup would revert UI edits on every `--reload` restart. Explicit
  `uv run python -m app.seed` instead, with `--file` and `--dry-run` flags.

**Files:** `seed/categories.toml` (new, 4 starter categories), `app/seed.py` (new), `tests/test_seed.py`
(new, 17 tests), `How-to-guide.md` (Step 1 rewritten; stale "0 categories" line corrected).

**Validation reuse:** `load_seed_file` parses into `CategoryCreate` from `app/schemas.py` — the same model
`POST /categories` uses — so the file is held to identical rules (non-empty name, color ≤32 chars,
`sort_order >= 0`) rather than re-implementing checks. Duplicate names within the file are rejected
explicitly, since they'd otherwise silently collapse via the upsert.

**Verified:** `ruff format` + `ruff check` clean; `mypy app` strict clean (20 files); `pytest` 115 passed
(17 new). End-to-end against the real DB: `--dry-run` → 4 inserted (no write), apply → 4 inserted, re-run →
0 inserted / 4 updated (idempotent). `GET /api/categories` through the running Vite proxy returns all four
with correct colors and `sort_order`.

**Agents:** none — built inline per session instruction not to spawn agents unless asked.

**Still open (unrelated, pre-existing):** `/today` intermittently renders "An unexpected error occurred."
That string exists only at `app/main.py:89` (the catch-all 500 handler), but all three endpoints TodayPage
calls return 200 to curl, so it was not reproducible from the shell. Needs the `logger.exception` traceback
from the uvicorn terminal to diagnose. Not addressed by this branch — an empty category list was ruled out
as the cause.

---

## Branch: `fix/sqlite-thread-affinity`

**Goal:** fix `sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that same
thread` returning 500s from the API under `npm run dev`. **This closes the "Still open" item from the
previous entry** — the intermittent "An unexpected error occurred." banner was this bug all along, surfaced
via the catch-all 500 handler at `app/main.py:89`.

**Root cause:** `_connect()` in `app/db.py` called `sqlite3.connect()` with the default
`check_same_thread=True`. The sync yield-dependency `get_db` (`app/deps.py`) and the sync `def` route
handlers are dispatched by Starlette as *separate* threadpool tasks with no thread affinity, so the
connection was created on one thread and used on another.

**Why it was invisible to the test suite:** `TestClient` runs an entire request inside a single portal
thread, so the dependency and the handler always shared a thread. The exact request that failed under
uvicorn returned 200 under `TestClient`. No `TestClient`-based test could ever have caught this.

**Reproduction (before fix):** 30 parallel `GET /tags` against real uvicorn → 25 × 500, 5 × 200. One
sequential request → 200, which is why it looked intermittent.

**Fix (`app/db.py` only):** `check_same_thread=False` (safe — one connection per request, used strictly
serially across threads, never shared between concurrent requests), `timeout=30` busy timeout (needed
because unblocking the threading issue exposes real write contention under autocommit), and
`PRAGMA journal_mode = WAL` so readers don't block on writers.

**Verified after fix:** 30 parallel reads → 30 × 200; 40 mixed parallel `POST /tags` + `GET /today` →
all 200/201, zero `ProgrammingError`, zero `database is locked`. `ruff format` + `ruff check` clean,
`mypy app` clean (20 files), `pytest` 117 passed.

**Regression test:** `tests/test_sqlite_thread_affinity.py` (new) launches the app under real uvicorn in a
subprocess on an ephemeral port against a `tmp_path` database, then fires concurrent requests through a
thread pool. Marked `slow` (marker registered in `pyproject.toml`) so it can be deselected. Independently
confirmed it FAILS with `check_same_thread=False` removed and passes with it — a `TestClient` test here
would have been worthless.

**`.gitignore`:** added `*.db-wal` / `*.db-shm`, the sidecar files WAL mode creates.

**Router audit (all 8 DB-touching routers, one agent each):** no blocking issues. No router uses its
connection from two threads *concurrently* (only serial handoff), no `BEGIN IMMEDIATE` block straddles a
thread switch or leaks on an error path, and no endpoint returns a lazy cursor consumed after the handler
returns (checked specifically in `exports.py` / `reports.py`).

**Pre-existing issues found during the audit, NOT addressed here:**
- `today.py` `get_today` issues 5+ unguarded SELECTs with no snapshot; now that real concurrency works, a
  concurrent write can interleave and yield an internally inconsistent response. Wants a deferred
  transaction if "Today" is meant to be one consistent instant.
- Check-then-insert TOCTOU in `tags.py` `create_tag`/`update_tag` and `categories.py`
  `create_category`/`update_category`. Currently fails *safely* (409) via the UNIQUE constraint +
  `IntegrityError` catch, so it's papered over rather than correct.
- `entries.py` `delete_entry` does check-then-delete without a `transaction()` wrapper — benign
  (idempotent) but inconsistent with the rest of the router.
- `exports.py` `db.backup()` holds a read lock for the duration of the copy; fine now, notable for a large DB.

**Agents:** `python-pro` ×9 (1 implement, 8 read-only per-router audits), `test-automator` ×1,
`code-reviewer` ×1.

---

## Branch: `fix/today-consistent-snapshot`

**Goal:** close the read-consistency follow-up logged on the previous branch — `/today` could return an
internally inconsistent response under concurrent writes.

**Why it became reachable:** `fix/sqlite-thread-affinity` (PR #12) made the app genuinely concurrent
(`check_same_thread=False` + WAL). Before that, the threading bug 500'd most concurrent requests, so this
interleaving was masked rather than absent.

**Problem:** `get_today` issued 5+ separate SELECTs — settings timezone, today's entries, running timer,
recent categories, recent tags — plus a category and tags lookup *per entry* inside `entry_from_row`. With
`isolation_level = None` (autocommit), every statement committed independently, so a concurrent writer
could commit between any two of them: e.g. a `running_timer` contradicting the already-read entries list,
or tags fetched for an entry that was concurrently edited.

**Fix:** new `read_snapshot(db)` context manager in `app/repo.py`; `get_today` wraps its whole body in it.

**Key design call — `BEGIN DEFERRED`, not `BEGIN IMMEDIATE`.** The existing `transaction()` helper uses
`BEGIN IMMEDIATE`, which takes the write lock up front. Reusing it here would have been the obvious
"simplification" and would have been wrong: it would serialize every `/today` read against all writers and
throw away the benefit of WAL. `BEGIN DEFERRED` takes no lock and, under WAL, establishes a stable read
snapshot at the first read. `read_snapshot` always ends the transaction (COMMIT/ROLLBACK) — a leaked read
transaction under WAL blocks checkpointing.

**Re-entrancy guard:** `read_snapshot` raises a clear `RuntimeError` if the connection is already in a
transaction. SQLite has no nested transactions, and since this wraps an entire route handler, a repo
helper that later grew its own transaction would otherwise fail with the opaque
`cannot start a transaction within a transaction`. Added after code review flagged it as a latent footgun.

**Verified — the four properties that matter, checked directly against a temp WAL DB before writing tests:**
snapshot isolation holds (concurrent committed write invisible inside the block, visible after); writers
are NOT blocked while a snapshot is held (0.1ms, confirming DEFERRED); the exception path leaves
`in_transaction == False`; and nesting raises the explicit error. Regressing `BEGIN DEFERRED` to
`BEGIN IMMEDIATE` makes the new tests fail (in 62s — each blocked writer waits out the 30s busy timeout).

**Tests:** `tests/test_read_snapshot.py` (new, 5 tests). `ruff format` + `ruff check` clean, `mypy app`
clean (20 files), `pytest` 122 passed. End-to-end under real uvicorn: 30 parallel `GET /today` → all 200;
40 mixed parallel `/today` + `POST /tags` → all 200/201, zero nested-transaction errors, zero
`database is locked`, zero tracebacks.

**Deliberately NOT changed:** `reports.py` and `exports.py` have the same multi-read pattern and could
adopt `read_snapshot`, but were kept out of scope. `transaction()` did not get the same re-entrancy guard —
worth adding for symmetry, but it is just-merged code and untouched here.

**Known non-blocking nit (accepted):** `ZoneInfo(tz_name)` and `datetime.now(tz)` run inside the snapshot
block, holding it open marginally longer than strictly needed. Moving them out would decouple the timezone
read from the snapshot for negligible gain on a single-user local app, so it was left as-is.

**Agents:** `python-pro` ×1 (implement), `test-automator` ×1, `code-reviewer` ×1. Orchestration was driven
from the main thread (no `architect-orchestrator` sub-agent), so there is no separate token figure for it.

---

## Branch `fix/category-colors-and-picker-clipping` — category colours + clipped category dropdown

Two user-reported frontend bugs, both root-caused before any code was written.

**Bug 1 — every category rendered slate grey.** `frontend/src/utils/categoryColor.ts` resolved a
category's stored `color` against a fixed set of 12 named palette keys (`blue`, `teal`, …) and fell back
to `slate` for anything else. But real categories store raw hex: `seed/categories.toml` ships `#e3db38`,
`#F59F00`, `#384ad2`, `#f31717`, `#12B886`, and `app/schemas.py` documents `color` as a free-form token
("hex code or CSS name"). So the fallback swallowed every seeded category. `categoryColorVar()` now
handles three cases: named key → theme-aware `var(--cat-*)` (unchanged), anchored-regex-validated hex
(`#RGB`/`#RGBA`/`#RRGGBB`/`#RRGGBBAA`) → passthrough, anything else/null → `slate`. The regex is a real
guard, not cosmetic: the value flows into an inline `style` and is interpolated into the `color-mix()`
expression in `categoryChipTint()`, which an unvalidated string would break.

**Bug 2 — could not scroll/reach categories when editing a saved entry.** `CategoryPicker`'s options list
was `position: absolute` inside the picker root. It already had `max-height: 240px; overflow-y: auto`, so
the popover was not the problem — an ancestor was: `.list` sets `overflow: hidden` in BOTH
`pages/Today/TodayPage.module.css` and `components/DayGroup/DayGroup.module.css` (there to clip the
bordered list's rounded corners). Inline-editing a row put the popover inside that clip. Fixed by
portalling the list to `document.body` via `createPortal` with `position: fixed`, positioned from the
trigger's `getBoundingClientRect()`, flipping above the trigger when there is no room below, clamped
horizontally into the viewport, and repositioned on `resize` + capture-phase `scroll`. Rounded corners are
untouched.

**The subtle part:** portalling moves the popover OUT of `rootRef`, so the existing outside-click handler
(`rootRef.contains(target)`) would have closed the popover on its own mousedown, making every option
unclickable. The handler now also checks `popoverRef`. Two regression tests pin this down specifically —
note `fireEvent.click` does not fire `mousedown`, so the naive click test passes even with the bug; the
guards fire `mouseDown` explicitly (inside → stays open, outside → closes).

**Tests:** `utils/categoryColor.test.ts` (new) and `components/CategoryPicker/CategoryPicker.test.tsx`
(new). `npm run lint` clean, `prettier --check` clean, `npm test` 60/60 pass.

**Pre-existing, left alone:** `npx tsc -b --noEmit` reports 2 errors in `pages/Reports/ReportsPage.test.tsx`
(missing `entry_count` in `ReportDayBreakdown` fixtures). Confirmed present on `main` by stashing — out of
scope for this branch.

**Not done (accepted):** the picker still has no focus management (focus does not move into the listbox on
open or return to the trigger on close). That gap predates this change; code review flagged it as
non-blocking.

**Agents:** `frontend-developer` ×1 (implement, 38,680 tokens — terminated early by an API 529 after
writing the implementation and both test files; verification, the viewport clamp, and the two mousedown
regression tests were completed from the main thread), `code-reviewer` ×1 (24,430 tokens, no blocking
issues). Orchestration driven from the main thread. Total sub-agent usage: 63,110 tokens.

---

## Branch `feat/mandatory-category-and-comment` — mandatory category + optional Comment field

Two user requests, resolved after clarifying an ambiguity in the original ask.

**Clarification that shaped the work.** The request said the Comment field "should stay in the categories
table". That is not expressible: `categories` has one row per category, shared by many entries, so a
comment stored there would be identical for every entry using that category. Asked the user; they
confirmed they meant `entries`, and that the existing `notes` column should be reused rather than a new
column added. They also chose the strictest enforcement for the mandatory category (DB-level `NOT NULL`)
and explicitly authorized destroying existing entries to get there.

### Mandatory category

`entries.category_id` is now `INTEGER NOT NULL REFERENCES categories (id) ON DELETE RESTRICT`. `ON DELETE
SET NULL` is no longer legal under `NOT NULL`; `RESTRICT` is safe because the app never hard-deletes
categories — `app/routers/categories.py` only exposes `/deactivate` (`is_active = 0`), and no
`DELETE /categories/{id}` route exists.

API: `EntryCreateManual.category_id` and `TimerStartRequest.category_id` became required; `EntryRead.category`
became non-null. `EntryUpdate.category_id` / `TimerStopRequest.category_id` stay `int | None = None` because
`model_dump(exclude_unset=True)` uses `None` to mean "field absent" in PATCH semantics — but an *explicitly*
sent `null` is now rejected with a `ValidationError`, mirroring the existing `start_ts cannot be null` guard.
Without that check a PATCH could clear a category and surface a raw `IntegrityError` as a 500 instead of a
clean 4xx.

**Migration** (`app/schema.py`): all DDL uses `CREATE TABLE IF NOT EXISTS`, so an existing database would
never pick up the new constraint. `_migrate_entries_category_not_null` detects the old shape via the
`notnull` flag from `PRAGMA table_info(entries)` and performs the standard SQLite 12-step rebuild —
`entries_new` with the new DDL, copy rows `WHERE category_id IS NOT NULL`, drop, rename, recreate
`idx_entries_start_ts` + `idx_entries_category_id` (indexes die with the dropped table). `PRAGMA
foreign_keys` is toggled OFF/ON around it (SQLite only honors that pragma outside a transaction) with
`isolation_level = None` for explicit transaction control. Rows with a NULL category cannot satisfy the new
constraint and are deleted along with their `entry_tags` rows. Runs from `init_db` on every startup and is
a no-op once migrated. Ordering matters: `create_schema` runs first, so on a fresh DB the table is already
created in the new shape and the migration correctly does nothing.

**Verified against a copy of the real database**, not just fixtures: categorized rows preserved, schema
`NOT NULL`, both indexes recreated, `PRAGMA foreign_key_check` clean.

Frontend mirrors all of it: `CategoryPicker` gained a `required` prop that hides the "No category" option
and marks the placeholder; Start/Save are disabled until a category is picked, always paired with an
explanatory hint so the disabled button is never a dead end; `StartPayload.category` and
`EntryRowSaveValues.category` tightened to non-null; now-dead `entry.category && …` checks removed.
`ReportCategoryBreakdown.category` was deliberately LEFT nullable on both sides — that bucket just becomes
unreachable, and leaving it kept the diff contained.

### Comment field

No schema change. The existing `entries.notes` column already round-trips through create/update/timer-start/
timer-stop, so it is reused as-is. Only the user-facing copy says "Comment"; the wire and prop names stay
`notes` to match `app/schemas.py`, with a comment at each site noting the mismatch is deliberate. It is now
editable in all four places an entry can be created or edited — quick-add, manual entry, running timer, and
inline entry edit (the last two previously had no notes field at all).

**Bug found and fixed during review of the agent's output:** the running-timer comment input is controlled
by `runningEntry.notes`, i.e. the value round-tripped from the server on every keystroke. It was calling a
trimming normalizer per keystroke, so typing a space had it stripped and echoed back immediately — making
multi-word comments impossible to type. Split into `normalizeNotes` (submit-time, trims) and
`normalizeNotesLive` (per-keystroke, only collapses truly-empty to `null`), with two regression tests.
`EntryRow`'s comment input was already correct — it edits local state and trims only on save.

**Tests:** backend 132 passed (was 122); frontend 68 passed (was 60). `ruff check`, `mypy app`, `eslint`,
`prettier` all clean.

**Non-blocking, accepted as-is:** the migration's discard notice uses `print()` rather than a logger (the
app has no logger configured); `entry_from_row` raises `RuntimeError` on an unresolvable category, which is
unreachable under the FK constraint and is caught by the catch-all handler at `app/main.py:72` that returns
a generic `internal_error` envelope without leaking internals.

**Pre-existing, still not fixed:** the same 2 `tsc` errors in `pages/Reports/ReportsPage.test.tsx`.

**Agents:** `python-pro` ×1 (backend + backend tests, 126,804 tokens), `frontend-developer` ×1 (frontend +
frontend tests, 98,011 tokens), `code-reviewer` ×1 (44,017 tokens, no blocking issues). Orchestration,
independent verification, the live-typing bug fix, its regression tests, and the `aria-required` a11y nit
were done from the main thread. Total sub-agent usage: 268,832 tokens.
