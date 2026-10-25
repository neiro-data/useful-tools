# README_AGENT.md

Internal notes for an AI agent that changes this code. A person who only runs the tool does not
need this file. Referenced from [README.md](README.md).

## Module map

| File | Responsibility |
| --- | --- |
| `src/ddl_to_drawio/cli.py` | `argparse` front end. Reads the input, calls the parser, calls the emitter, writes the output, returns the exit code. |
| `src/ddl_to_drawio/model.py` | The dataclasses `TableId`, `Column`, `Table`, `ForeignKey` and `Schema`. No behaviour beyond two helpers on `Table`. |
| `src/ddl_to_drawio/parser.py` | Walks the `sqlglot` abstract syntax tree (AST). Holds `DEFAULT_SCHEMA`, `DEFAULT_DIALECT` and `SUPPORTED_DIALECTS`. |
| `src/ddl_to_drawio/layout.py` | Computes the box position and the box size of each table. Holds `PK_PREFIX` and `FK_PREFIX`. |
| `src/ddl_to_drawio/emitter.py` | Builds the `mxfile` XML document. |
| `tests/test_parser.py`, `tests/test_emitter.py`, `tests/test_cli.py` | The three test modules. |
| `tests/fixtures/sample_plants.sql`, `tests/fixtures/sample_mysql.sql` | The two DDL fixtures. |

## Contracts you must not break

- **The emitter never imports `sqlglot`.** `emitter.py` and `layout.py` import only
  `ddl_to_drawio.model`. The docstrings of `model.py` and `emitter.py` state this rule.
- **`PK_PREFIX` and `FK_PREFIX` have one home.** They live in `layout.py`. `_table_widths()` in
  `layout.py` measures the label, and `_column_name_label()` in `emitter.py` writes the label. A
  change to one function needs the same change to the other, or the box becomes too narrow.
- **The output is deterministic.** The same input gives a byte-identical file. `compute_layout()`
  sorts the tables by `(schema, name)`, `build_mxgraph_xml()` sorts the foreign keys, and `_slug()`
  appends the first 8 hexadecimal characters of a SHA-256 digest to keep cell identifiers stable
  and free of collisions.
- **Foreign keys resolve after the parse.** `parse_ddl()` collects `_PendingForeignKey` records
  first. It resolves them only after every `CREATE TABLE` statement is read, because
  `REFERENCES parent` without a column list needs the primary key of the parent table.

## draw.io cell contract

The emitter writes four kinds of `mxCell`:

| Cell | Style |
| --- | --- |
| Table box | `shape=table;startSize=30;container=1;collapsible=0;childLayout=tableLayout;fixedRows=1;rowLines=0;fontStyle=1;align=center;resizeLast=1;html=1;fillColor=#B8B8B8;` |
| Column row | `shape=tableRow;horizontal=0;...;fillColor=#FFFFFF;collapsible=0;dropTarget=0;points=[[0,0.5],[1,0.5]];portConstraint=eastwest;top=0;left=0;right=0;bottom=1;html=1;` |
| Name part and type part | `shape=partialRectangle;connectable=0;fillColor=none;...` (`_PART_STYLE`), the name part with `fontStyle=1;` |
| Foreign-key edge | `edgeStyle=entityRelationEdgeStyle;html=1;endArrow=ERmany;startArrow=ERone;rounded=0;` |

Two rules cost this project a bug fix each. Keep them:

- A `shape=tableRow` cell keeps an **empty** `value`. The label belongs to the child
  `shape=partialRectangle` part. A label on the row itself draws rotated 90 degrees.
- Each part carries an `mxRectangle` with `as="alternateBounds"`. Without it draw.io re-flows the
  part widths.
- `bottom=1` on the row draws the separator line. `collapsible=0` on the table box stops a viewer
  from hiding the rows.

## Known drift

- `Column.not_null` and `Column.is_unique` are parsed and stored, but no module reads them.
  `NOT NULL` and `UNIQUE` do not appear in the diagram. Render them, or drop the fields.
- The dialect check at the top of `parse_ddl()` is unreachable from the command line, because
  `argparse` rejects a bad value first. It guards direct callers of the library. Its own docstring
  says so.
- `layout.py` carries a comment about an "old single 24px LABEL_PADDING". That constant no longer
  exists. `NAME_PADDING` and `TYPE_PADDING` replaced it.

## Verified state

Verified on 2026-09-02 with `uv run pytest`, `uv run ruff check .` and `uv run mypy`:

- 57 tests pass. `ruff` and `mypy` (strict) report no issue.
- `uv run ddl-to-drawio tests/fixtures/sample_plants.sql` gives 4 table boxes, 18 column rows and
  3 foreign-key edges.
- Two runs on the same fixture give byte-identical output.

## Docs map

| File | Purpose |
| --- | --- |
| [README.md](README.md) | The human entry point. What the tool is, how to run it, what it supports. |
| [README_AGENT.md](README_AGENT.md) | This file. Module map, code contracts and known drift. |
| [claude_interaction_steps.md](claude_interaction_steps.md) | The branch-by-branch history of the agent sessions that built the tool. |
