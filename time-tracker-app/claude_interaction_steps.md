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
