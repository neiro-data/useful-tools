# tool-sql-to-drawio

## Resume

CLI that converts a SQL DDL dump (PostgreSQL, MySQL, Trino, Presto, or DuckDB) into a draw.io
(`.drawio`) ER diagram, with FK edges anchored to individual column rows (not just table boxes).
Stack: Python 3.11+, `uv`, `sqlglot` (parsing), `xml.etree.ElementTree` (emission). Run: `uv sync`, then
`uv run ddl-to-drawio tests/fixtures/sample_plants.sql`. Tests: `uv run pytest`.

## Install

```bash
uv sync
```

## Usage

```bash
# writes sample_plants.drawio next to the input
uv run ddl-to-drawio tests/fixtures/sample_plants.sql

# explicit output path
uv run ddl-to-drawio dump.sql -o erd.drawio

# stdin -> stdout
cat dump.sql | uv run ddl-to-drawio - -o -

# only include one schema
uv run ddl-to-drawio dump.sql --schema public

# parse a non-PostgreSQL dialect
uv run ddl-to-drawio dump.sql --dialect mysql
```

## Supported DDL / limitations

- Dialects: `postgres` (default), `mysql`, `trino`, `presto`, `duckdb`, selected via `--dialect`
  (lowercase, e.g. `--dialect mysql` — not `MySQL`) and passed straight to `sqlglot(read=...)`,
  AST-based — no regex on the main parse path.
  Dialects without schema qualification (e.g. MySQL) land under the default schema `public`.
- FK edges are only drawn for `FOREIGN KEY ... REFERENCES` constraints actually present in the
  DDL. Trino/Presto/DuckDB DDL typically omits FK constraints because those engines don't enforce
  them, so diagrams generated from those dialects are often tables-only — that's a property of the
  source DDL, not a limitation of this tool.
- `CREATE TABLE` columns, types, `NOT NULL`, `PRIMARY KEY` (inline and table-level), `UNIQUE`.
- Foreign keys in all three common forms found in real pg_dump output: out-of-line
  `ALTER TABLE ONLY ... ADD CONSTRAINT ... FOREIGN KEY ... REFERENCES ...`, inline column-level
  `REFERENCES`, and inline table-level `FOREIGN KEY (...) REFERENCES ...`.
- Schema-qualified and unqualified table names are normalized to the same identity (default
  schema `public`), so an `ALTER TABLE public.foo` resolves against an unqualified
  `CREATE TABLE foo`. Unquoted identifiers are lowercase-folded (Postgres semantics); quoted
  identifiers are preserved as-is.
- Ignored (by design, not an error): `SET`, `CREATE INDEX`, `CHECK` constraints, comments.
- A foreign key referencing a table absent from the dump is skipped with a warning on stderr,
  not a crash.
- Layout is a deterministic grid sized from each table's column count — good enough to open
  without overlaps. For a nicer arrangement, open the file in draw.io and run
  **Arrange → Layout → Organic**.

## Output format

Each table becomes an `mxCell` `shape=table` vertex with a light grey (`#B8B8B8`) header band;
each column becomes a child `mxCell` `shape=tableRow` split into a bold name sub-column and a
regular-weight type sub-column, aligned to the same width within each table. Foreign-key edges
connect the specific child-column and parent-column cells (crow's-foot notation:
`endArrow=ERmany;startArrow=ERone`), so relationships stay anchored to the correct rows even if
you rearrange table boxes in draw.io.

Open the generated `.drawio` file directly in [draw.io](https://app.diagrams.net/) (or the
desktop app) via File → Open.
