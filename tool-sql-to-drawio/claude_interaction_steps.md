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

## fix/drawio-table-row-format (branched from `tool-sql-to-drawio`)

Purpose: the emitted `.drawio` rendered wrong in app.diagrams.net — every column label drawn rotated 90°
and overlapping, table rows appearing empty.

- Root cause: `shape=tableRow` cells carried the column label in their own `value` while setting
  `horizontal=0`. draw.io requires an empty row value plus a child `shape=partialRectangle` part holding
  the label.
- Pipeline: plan skipped (bounded to `emitter.py`/`layout.py`, read inline) → `python-pro` implemented →
  `test-automator` + `code-reviewer` run in parallel → fresh `python-pro` fixed review defects from
  `handoff-fix-drawio-table-row-format.md`.
- `code-reviewer` found 2 blockers (label part missing draw.io's canonical style/`alternateBounds`;
  width heuristic never measured the table header) and 6 should-fix/nit, incl. two unrelated style flips
  bundled in by the first pass (`bottom=1`→`0` killed row separators, `collapsible=0`→`1` let viewers
  hide a table's rows). All fixed.
- Also added per-table width sizing from the longest label (clamped 220–460) with per-grid-column x
  offsets, and shared `PK_PREFIX`/`FK_PREFIX` constants so label text and width math can't desync.
- Gates re-run by the orchestrator: ruff format/check, mypy, pytest 38/38 clean; CLI on the fixture
  byte-identical across two runs. No local drawio renderer — visual check done by Nelson in the browser.
