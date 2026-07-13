# useful-tools

A repository that collects multiple useful tools for day-to-day use. Each tool is its own small,
self-contained project living in its own subdirectory — there is no shared build system or dependency
manifest across the repo, so treat each tool independently.

## Tools

### [`time-tracker-app/`](time-tracker-app/)

A personal, offline-first time tracker that runs entirely on `localhost`: a **FastAPI + SQLite**
backend and a **React** single-page app frontend, with no cloud dependency. It supports time tracking
against categories and tags, Today/Week/Month views, period Reports (with breakdowns and a narrative
summary), data Exports (HTML/CSV/SQLite backup), and configurable Settings. See
[`time-tracker-app/README.md`](time-tracker-app/README.md) for setup and usage.
