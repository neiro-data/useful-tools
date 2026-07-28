# Claude interaction steps

## feat/ddl-to-drawio-erd (branched from `tool-sql-to-drawio`)

Purpose: new `tool-sql-to-drawio/` CLI — PostgreSQL DDL dump → draw.io `.drawio` ER diagram, FK edges
anchored to individual column rows.

- Design came from a prior session, stored in memory `ddl-to-drawio-erd-generator`; Nelson supplied the
  dialect (PostgreSQL) and a 4-table sample dump, saved as `tests/fixtures/sample_plants.sql`.
- Decided: lives in this repo (not a new repo under `REPOS`); column-level anchoring via `shape=table`
  mxGraph XML, not the simpler drawio CSV-import format.
- Pipeline: plan stage skipped (already scoped) → `python-pro` implemented → `test-automator` verified
  independently → `code-reviewer` reviewed → fresh `python-pro` fixed defects from a handoff file.
- `test-automator` found a composite-FK bug (every source column paired to `target_columns[0]`).
- `code-reviewer` found 1 blocker (`REFERENCES parent` without a column list silently dropped the FK)
  and 2 should-fix (cell-id slug collisions; `zip(strict=False)` silently truncating mismatched
  composite FKs). All fixed with regression tests.
- Gates re-run by the orchestrator: ruff format/check, mypy, pytest 29/29 clean; end-to-end run on the
  fixture verified 4 table vertices, 18 column rows, 3 column-anchored crow's-foot edges, byte-identical
  across two runs.
