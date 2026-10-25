# scripts-guide.md

Every command of this project, grouped by target. Referenced from [README.md](README.md).

## Backend

```bash
uv sync
uv run uvicorn app.main:app --reload
```

The API answers at `http://127.0.0.1:8000`. The health check is at
`http://127.0.0.1:8000/health`. `app/API_CONTRACT.md` holds the paths, the bodies, the status
codes and the error envelope.

## Frontend

In a second terminal, from `frontend/`:

```bash
cd frontend
npm install
npm run dev
```

The single-page application answers at `http://localhost:5173`, the default port of Vite. It
proxies every `/api/*` call to the backend above. `frontend/README.md` holds the proxy and origin
configuration.

Both halves must run for the application to work end to end.

## Docker

```bash
docker compose up --build
```

| Address | Serves |
| --- | --- |
| `http://localhost:8080` | The frontend behind nginx. It proxies `/api` to the backend container. |
| `http://localhost:8000` | The backend directly, for debugging. |

The SQLite file is bind-mounted from `./time_tracker.db` on the host into the backend container.
Docker therefore reads and writes the same file as a local `uv run uvicorn` run. The data survives
`docker compose down` and `up`, and any SQLite tool on the host can open it.

**Do not run the Docker backend and a local `uv run uvicorn` against that file at the same time.**
SQLite does not accept concurrent writers.

Categories are not seeded on start. The seeding is opt-in, and `app/seed.py` performs it. Seed
once after the first boot.

```bash
docker compose exec backend python -m app.seed
```

## Quality checks

```bash
uv run ruff check .    # lint
uv run ruff format .   # format
uv run mypy app        # check the types
uv run pytest -q       # run the tests
```

`tests/` holds 20 test modules. Each test gets a fresh SQLite file in `tmp_path`, so the tests
isolate themselves from the real database.

## The dummy database

The tests isolate themselves. Manual work does not. A `curl` against an endpoint, the
single-page application, or a script all reach whatever `TIME_TRACKER_DATABASE_PATH` points at.
By default that is the real `time_tracker.db`. Generate a disposable database instead.

```bash
uv run python -m app.dummy_data                  # write ./dummy.db with about 4 weeks of data
uv run python -m app.dummy_data --days 90        # a quarter, so Reports has enough data
uv run python -m app.dummy_data --running-timer  # also leave one entry open, as if a timer ran
uv run python -m app.dummy_data --reset          # delete the file and build it again
```

Then run the backend against it.

```bash
TIME_TRACKER_DATABASE_PATH=dummy.db uv run uvicorn app.main:app --reload
```

`dummy.db` is gitignored. It is regenerated, never committed.

The generator cannot overwrite your real data. See
[README_AGENT.md — The dummy-data guard](README_AGENT.md#the-dummy-data-guard).

## Configuration

`pydantic-settings` loads the settings from environment variables with the prefix
`TIME_TRACKER_`, and optionally from a local `.env` file, which is not committed.

| Setting | Default |
| --- | --- |
| `TIME_TRACKER_DATABASE_PATH` | `time_tracker.db` |
| CORS origins | The origins of the React development server. |

## Other guides in this project

| File | Content |
| --- | --- |
| `How-to-guide.md` | A first-run walkthrough of the application. |
| `sqlite-command-guide.md` | A reference for the `sqlite3` CLI and its SQL dialect. |
| `test_reports/README.md` | The sample report output, and how it was generated. |
| `app/API_CONTRACT.md` | The HTTP contract of the API. |
| `design/DESIGN_SYSTEM.md`, `design/screens.md` | The design system and the screen wireframes. |
