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
