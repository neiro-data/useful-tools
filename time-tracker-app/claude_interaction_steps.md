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
