> Date: 27/08/2026
> Creator: Nelson Eiró
> version v1.0

# Time Tracker App

## Resume

Time Tracker App is a personal, offline-first time tracker. It runs on `localhost` only. There is
no cloud dependency. All data stays in one local SQLite file.

- **Backend:** FastAPI and SQLite, in `app/`. It implements [`app/API_CONTRACT.md`](app/API_CONTRACT.md).
- **Frontend:** a React single-page application, in `frontend/`. It has the Today, Week, Month,
  Reports and Settings screens. See [`frontend/README.md`](frontend/README.md).
- **Entry point:** `app.main:app` for the API, and `frontend/` for the interface.
- **Host requirements:** Python 3.11 or later, [`uv`](https://docs.astral.sh/uv/), Node.js and npm.
  Docker Compose is an alternative to both.

The application is at version v1.0. Most of the known bugs are corrected. The reports dropped the
Outlook compatibility, because the report graphics need inline `<svg>` and a `<style>` block. You
can still export a report as Markdown, HTML or PDF, and send it by email. A database export is
always available.

## Agent read

If you are an AI agent, read also [README_AGENT.md](README_AGENT.md).

## Quick start

The application has two halves. Both must run.

1. Install the backend dependencies and start the API.

   ```bash
   uv sync
   uv run uvicorn app.main:app --reload
   ```

   The API answers at `http://127.0.0.1:8000`. The health check is at `/health`.

2. In a second terminal, start the frontend.

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

   The interface answers at `http://localhost:5173`. It proxies every `/api/*` call to the API.

For Docker, the quality checks, the dummy database and the configuration, see
[scripts-guide.md](scripts-guide.md).

## Time tracking

You log an entry against one category and any number of tags. A live timer records the current
task. The Today, Week and Month screens show the tracked time per day, week and month. The Week
header shows the ISO calendar week, from `CW 01` to `CW 53`. You can edit an entry in place,
including its start time and its end time.

## Reports

A report summarizes one period: a week, a month or a quarter. It breaks the time down per category
and per tag. It draws daily bars, zero-filled weekly bars, a stacked hours-by-category chart and an
entry-count line chart. It also writes a rule-based narrative of the period. The month bars and the
quarter bars carry a calendar-week label, such as `CW 27`, and the full date range on hover.

## Exports

Five downloads are available. `app/routers/exports.py` builds them all.

| Export | Content |
| --- | --- |
| `GET /exports/report.html` | The report as one self-contained HTML document, with the charts. |
| `GET /exports/report.md` | The report as Markdown, in a raw format. |
| `GET /exports/report.pdf` | The report as a PDF document. |
| `GET /exports/entries.csv` | Every completed entry, as CSV. |
| `GET /exports/backup` | A copy of the raw SQLite database. |

The HTML export has no Outlook-compatibility constraint. It uses an inline `<style>` block and
inline `<svg>`, and no export renders a data table.

## Settings

The Settings screen holds four values: the timezone, which sets the day boundaries; the first day
of the week; the default entry mode; and the default export format. The `settings` table holds
exactly one row. See [scripts-guide.md — Configuration](scripts-guide.md#configuration) for the
environment variables that override the defaults.

## Schema

The database is SQLite with six tables: `categories`, `tags`, `entries`, `entry_tags`,
`report_exports` and `settings`. The canonical data definition lives in `app/db_schema.py`, which
also runs the idempotent initialization and the migrations.

[SCHEMA.md](SCHEMA.md) holds the entity-relationship diagram, the
[conventions](SCHEMA.md#conventions) to read before you write a query, the
[indexes](SCHEMA.md#indexes) and the [seed data](SCHEMA.md#seed-data).

## Layout

```
time-tracker-app/
├── app/                      # FastAPI backend: routers, schemas, storage, exports
│   └── API_CONTRACT.md       # the HTTP contract: paths, bodies, status codes, errors
├── frontend/                 # React single-page application (Vite + TypeScript)
│   └── README.md             # frontend stack, proxy and origin configuration
├── design/                   # DESIGN_SYSTEM.md, screens.md, tokens.css
├── docker/
│   └── nginx.conf            # the nginx configuration of the frontend container
├── seed/
│   └── categories.toml       # the declarative category seed
├── test_reports/             # sample report output, with a README.md that explains it
├── tests/                    # 18 pytest modules, plus conftest.py and _time_helpers.py
├── Dockerfile.backend        # the backend image
├── Dockerfile.frontend       # the frontend image, served by nginx
├── docker-compose.yml        # both containers, for the full stack
├── pyproject.toml            # the project manifest
├── uv.lock                   # the locked dependencies
├── README.md                 # this file: what the application is, and how to start it
├── README_AGENT.md           # the agent notes: module map, the dummy-data guard, docs map
├── scripts-guide.md          # every command, grouped by target
├── SCHEMA.md                 # the SQLite data model
├── How-to-guide.md           # a first-run walkthrough of the application
└── sqlite-command-guide.md   # a reference for the sqlite3 CLI and its SQL dialect
```
