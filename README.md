# useful-tools

## Resume

This repository collects five independent tools for day-to-day use. Each tool is a small,
self-contained project in its own subdirectory.

- **No shared stack.** The repository has no manifest, no build system and no test suite at its
  root. Four tools are Python projects managed by `uv`. One is a plain JavaScript userscript.
- **Treat each tool independently.** Run every command from inside the directory of the tool.
- **Host requirements:** `uv` for the Python tools. Docker for the time tracker. A userscript
  manager for the webpage time tracker.

## Tools

| Tool | What it does | Stack |
| --- | --- | --- |
| [`time-tracker-app/`](time-tracker-app/) | An offline-first personal time tracker on `localhost`. | FastAPI, SQLite, React |
| [`webpage-time-tracker-app/`](webpage-time-tracker-app/) | A userscript that tracks time on time-sink sites and nudges past a daily limit. | Plain JavaScript, plus a Tkinter settings app |
| [`tool-sql-to-drawio/`](tool-sql-to-drawio/) | Turns a PostgreSQL DDL dump into a draw.io ER diagram. | Python, `sqlglot` |
| [`tool-html-to-epub/`](tool-html-to-epub/) | Converts clean HTML into a deterministic EPUB 3. | Python, `EbookLib` |
| [`tool-pdf-to-epub/`](tool-pdf-to-epub/) | Converts a machine-readable PDF into a deterministic EPUB 3. | Python, PyMuPDF, pdfplumber, `EbookLib` |

### [`time-tracker-app/`](time-tracker-app/)

The application runs entirely on `localhost`, with no cloud dependency. It tracks time against
categories and tags. It offers Today, Week and Month views, period Reports with breakdowns and a
narrative summary, Exports to HTML, CSV and a SQLite backup, and configurable Settings. See
[`time-tracker-app/README.md`](time-tracker-app/README.md).

### [`webpage-time-tracker-app/`](webpage-time-tracker-app/)

Every tracked site carries its own daily limit. The counter for the current site is always
visible: dimmed below half of the limit, opaque as it climbs. The tool keeps 14 days of per-site
totals for the trend. It targets Tampermonkey on Chrome and Userscripts.app on Safari. See
[`webpage-time-tracker-app/README.md`](webpage-time-tracker-app/README.md).

### [`tool-sql-to-drawio/`](tool-sql-to-drawio/)

The tool reads `CREATE TABLE` statements and foreign-key constraints. It parses the SQL with
`sqlglot` and emits `mxGraphModel` XML. Each table becomes a real draw.io table shape. Each
foreign key becomes a crow's-foot edge, anchored to the individual column rows and not only to the
table boxes. See [`tool-sql-to-drawio/README.md`](tool-sql-to-drawio/README.md).

### [`tool-html-to-epub/`](tool-html-to-epub/)

The `html2epub` CLI reads a single file, or a directory of files in filename order. It sanitizes
the markup to XHTML-safe content, splits it into chapters at the headings, derives a nested table
of contents and a spine, and writes the archive through `EbookLib` behind an adapter layer. The
same input and configuration always produce a byte-identical output. Version 1 is text-first: no
images, no cover, no JavaScript, no CSS fidelity and no PDF. See
[`tool-html-to-epub/README.md`](tool-html-to-epub/README.md).

### [`tool-pdf-to-epub/`](tool-pdf-to-epub/)

The `pdf2epub` CLI extracts the text and the structure of a PDF and writes a byte-deterministic
EPUB 3. It shares the internal model, writer and validator contract of `tool-html-to-epub`.

It is not a visual-fidelity converter. It produces no fixed-layout EPUB. It gives no guarantee on
a magazine, a brochure or a diagram-heavy PDF, and it does not preserve footnotes or sidebars as
such. See [`tool-pdf-to-epub/README.md`](tool-pdf-to-epub/README.md).

## Layout

```
time-tracker-app/           FastAPI + SQLite + React, offline-first
webpage-time-tracker-app/   the userscript and its Tkinter settings app
tool-sql-to-drawio/         SQL DDL to a draw.io ER diagram
tool-html-to-epub/          HTML to EPUB 3
tool-pdf-to-epub/           PDF to EPUB 3
README.md                   this file - what each tool is
```
