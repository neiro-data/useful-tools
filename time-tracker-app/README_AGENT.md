# README_AGENT.md

The agent notes of this project: the dummy-data guard, the `app/` module map, and the known
documentation drift. Referenced from [README.md](README.md).

A human who only wants to run the application does not need this file. Read
[README.md](README.md) first.

## The dummy-data guard

`app/dummy_data.py` writes a disposable database. It must never write to the real one. The guard
in that module makes this safe. Three rules define it.

### The database carries a label

`app/db_schema.py` gives every database a `settings.database_label` column. The bootstrap function
`_seed_default_settings` writes `settings.app_name` into it, and the default of `app_name` in
`app/config.py` is `Time Tracker`.

`app/dummy_data.py` overwrites that label. The module constant is:

```python
DUMMY_DATABASE_LABEL = "DUMMY DATA (app.dummy_data)"
```

The private function `_brand_as_dummy` runs one `UPDATE settings SET database_label = ?`. It runs
directly after `init_db`, before the generator writes any entry.

### The guard reads the content, not the file name

`assert_safe_target(path)` opens the target file and reads the label back with
`read_database_label(path)`. It permits two conditions only:

- The label is `None`. The file does not exist, the file is empty, or the file has no settings row.
- The label is exactly `DUMMY DATA (app.dummy_data)`, the constant above.

In every other condition it raises `DummyDataError` and the command stops. A real database gives
the label `Time Tracker`, so the guard rejects it. A file that is not a SQLite database, or a
SQLite database with no `settings` table, also raises `DummyDataError`.

The file name has no part in this decision. `--path time_tracker.db` is therefore safe: the guard
reads the content of that file and refuses it. `--reset` calls `assert_safe_target` before it
unlinks the file, so a delete gets the same protection as a write.

### The generation is seeded and deterministic

The module constant `DEFAULT_SEED = 20260713` supplies the default of the `--seed` flag.
`generate()` builds one `random.Random(seed)` and passes it to every generator function. The same
arguments therefore produce the same database on every run.

`generate()` also clears `entry_tags`, `entries` and `tags` before it writes. A second run replaces
the data. It does not stack a second copy onto the first.

`tests/test_dummy_data.py` holds 15 tests over this behaviour. They cover the branding, the
determinism, the two refusal paths and the command-line interface.

For the commands, see
[scripts-guide.md — The dummy database](scripts-guide.md#the-dummy-database).

## The app/ module map

`app/API_CONTRACT.md` is the HTTP contract: the paths, the request bodies, the response bodies,
the status codes and the error envelope. Read it before you change a router or a schema.

| Module | Purpose |
| --- | --- |
| `app/__init__.py` | The package marker. It names the application. |
| `app/main.py` | The FastAPI entry point. It mounts the router, the CORS middleware and the exception handlers. |
| `app/api.py` | The root router. It includes every router of `app/routers/`. |
| `app/config.py` | The `Settings` class of `pydantic-settings`, with the `TIME_TRACKER_` prefix. |
| `app/db.py` | The SQLite connection helper. It defines no table. |
| `app/db_schema.py` | The storage layer: the DDL, the indexes, and the idempotent `init_db` and migrations. |
| `app/schemas.py` | The wire layer: the Pydantic v2 request and response models. |
| `app/repo.py` | The shared access helpers: row-to-model conversion, timestamp normalization, existence checks. |
| `app/deps.py` | The shared FastAPI dependencies of the routers, such as `get_db` and `DbDep`. |
| `app/errors.py` | The domain error types. `app/main.py` translates them into the error envelope. |
| `app/report_theme.py` | The design tokens of the report exports, transcribed from `design/tokens.css`. |
| `app/seed.py` | The category seeding from `seed/categories.toml`. The seeding is opt-in. |
| `app/dummy_data.py` | The dummy database generator and the guard above. |
| `app/routers/__init__.py` | The router package marker. |
| `app/routers/categories.py` | The `/categories` endpoints. |
| `app/routers/tags.py` | The `/tags` endpoints. |
| `app/routers/entries.py` | The `/entries` endpoints, for both entry modes. |
| `app/routers/timer.py` | The `/timer` endpoints, including the single-active-timer rule. |
| `app/routers/today.py` | The `/today` aggregation endpoint. |
| `app/routers/reports.py` | The `/reports` aggregation endpoints, and `get_reports_summary`. |
| `app/routers/settings.py` | The `/settings` endpoints. The table holds exactly one row. |
| `app/routers/exports.py` | The `/exports` downloads: the backup, the CSV, and the HTML, Markdown and PDF reports. |

Two points repay attention:

- **`db_schema.py` and `schemas.py` are different layers.** The first is the storage layer, in SQL.
  The second is the wire layer, in Pydantic. Each enforces its constraints on its own. A required
  field in one does not make the column `NOT NULL` in the other. Change both together.
- **`app/routers/exports.py` is the largest module**, at 1465 lines. It builds all five downloads
  on top of `get_reports_summary` in `app/routers/reports.py`.

[SCHEMA.md](SCHEMA.md) holds the data model that `app/db_schema.py` defines.

## Known documentation drift

Two docstrings in `app/` describe an earlier state of the tree. Do not trust them. Trust the code.

| Location | The stale claim | The tree |
| --- | --- | --- |
| `app/db.py`, the module docstring | A `TODO(schema-owner)` says a later module, "e.g. `app/migrations.py`", owns the schema and the migrations. | `app/db_schema.py` owns them now. `app/migrations.py` does not exist. |
| `app/routers/__init__.py`, the module docstring | The routers are "thin signature/docstring stubs" whose bodies "raise `NotImplementedError`". | All eight routers are implemented. No router body raises `NotImplementedError`. |

## Docs map

| File | Content |
| --- | --- |
| [README.md](README.md) | The human entry point: what the application is, the stack, and the first run. |
| [scripts-guide.md](scripts-guide.md) | Every command, grouped by target: the backend, the frontend, Docker, the quality checks, the dummy database, the configuration. |
| [SCHEMA.md](SCHEMA.md) | The SQLite data model: the diagram, the conventions, the indexes and the seed data. |
| [README_AGENT.md](README_AGENT.md) | This file: the dummy-data guard, the `app/` module map, and the documentation drift. |
