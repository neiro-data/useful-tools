# Time Tracker App

A personal, offline-first time tracker. It runs entirely on `localhost`: a **FastAPI** backend
with **SQLite** as the canonical data store, and a **React** single-page app frontend. There is no
cloud dependency — all data lives in a local SQLite file.

- **Backend:** FastAPI + SQLite (`app/`) — implements `app/API_CONTRACT.md`.
- **Frontend:** React SPA (`frontend/`) — Today, Week, and Month screens (see `frontend/README.md`).

## Project layout

```
time-tracker-app/
├── app/
│   ├── __init__.py
│   ├── main.py      # FastAPI app, CORS, health check, router wiring
│   ├── config.py    # pydantic-settings configuration (env-driven)
│   ├── api.py       # root API router (feature routers plug in here)
│   ├── db.py        # SQLite connection helper
│   ├── schema.py     # DB schema + idempotent init
│   ├── schemas.py     # Pydantic request/response models
│   ├── API_CONTRACT.md # endpoint contract (paths, bodies, status codes, error envelope)
│   └── routers/       # categories, tags, entries, timer, today
├── design/
│   ├── DESIGN_SYSTEM.md
│   ├── tokens.css      # CSS custom properties, imported directly by the frontend
│   └── screens.md      # Today/Week/Month wireframes + keyboard shortcuts
├── frontend/           # React SPA (Vite + TypeScript) — see frontend/README.md
├── tests/
├── pyproject.toml
└── uv.lock
```

## Requirements

- Python 3.11+ and [`uv`](https://docs.astral.sh/uv/) for the backend.
- Node.js + npm for the frontend (see `frontend/README.md`).

## Getting started

This app has two halves that both need to be running for the SPA to work end-to-end:

**1. Backend** — install deps and start the API server:

```bash
uv sync
uv run uvicorn app.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`, with a health check at
`http://127.0.0.1:8000/health`.

**2. Frontend** — in a second terminal, from `frontend/`:

```bash
cd frontend
npm install
npm run dev
```

The SPA will be available at `http://localhost:5173` (Vite's default) and proxies `/api/*` calls
to the backend above — see `frontend/README.md` for the proxy/origin config and full details.

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
