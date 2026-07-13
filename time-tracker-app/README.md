# Time Tracker App

A personal, offline-first time tracker. It runs entirely on `localhost`: a **FastAPI** backend
with **SQLite** as the canonical data store, and (in a later phase) a **React** single-page app
frontend. There is no cloud dependency — all data lives in a local SQLite file.

- **V1 backend:** FastAPI + SQLite (this scaffold).
- **Frontend:** React SPA, to be added in a later phase.

## Project layout

```
time-tracker-app/
├── app/
│   ├── __init__.py
│   ├── main.py      # FastAPI app, CORS, health check, router wiring
│   ├── config.py    # pydantic-settings configuration (env-driven)
│   ├── api.py       # root API router stub (feature routers plug in here)
│   └── db.py        # SQLite connection helper (schema owned elsewhere)
├── tests/
│   └── test_health.py
├── pyproject.toml
└── uv.lock
```

Database schema and migrations are intentionally **not** defined in this scaffold — see the
`TODO` in `app/db.py`. That is owned by a dedicated migration module added in a later phase.

## Requirements

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) for dependency management

## Getting started

Install dependencies (creates/syncs the `.venv`):

```bash
uv sync
```

Run the development server:

```bash
uv run uvicorn app.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`, with a health check at
`http://127.0.0.1:8000/health`.

## Development

```bash
uv run ruff check .      # lint
uv run ruff format .     # format
uv run mypy app          # type-check
uv run pytest -q         # run tests
```

## Configuration

Settings are loaded via `pydantic-settings` from environment variables (prefix
`TIME_TRACKER_`) and, optionally, a local `.env` file (not committed). Key settings include
`database_path` (defaults to `time_tracker.db`) and CORS origins for the future React dev server.
