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
