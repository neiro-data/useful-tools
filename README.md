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

### [`tool-sql-to-drawio/`](tool-sql-to-drawio/)

A **Python** CLI that turns a PostgreSQL DDL dump (`CREATE TABLE` + foreign-key constraints) into a
draw.io (`.drawio`) ER diagram. It parses the SQL with `sqlglot` and emits `mxGraphModel` XML in which
each table is a real draw.io table shape and each foreign key is a crow's-foot edge anchored to the
individual column rows, not just the table boxes. See
[`tool-sql-to-drawio/README.md`](tool-sql-to-drawio/README.md) for setup and usage.

### [`tool-html-to-epub/`](tool-html-to-epub/)

A **Python** CLI (`html2epub`) that converts clean HTML — a single file, or a directory of files read
in filename order — into a valid, deterministic EPUB 3. It sanitizes the markup to XHTML-safe
content, splits it into chapters at headings, derives a nested TOC and spine, and writes the archive
through `EbookLib` behind an adapter layer. The same input and config always produce byte-identical
output. Text-first: v1 excludes images, covers, JavaScript, CSS fidelity, and PDF. See
[`tool-html-to-epub/README.md`](tool-html-to-epub/README.md) for setup and usage.
