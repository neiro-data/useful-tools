# tool-sql-to-drawio

## Resume

A command-line tool that converts a SQL data definition language (DDL) dump into a draw.io
(`.drawio`) entity relationship (ER) diagram. Each foreign-key edge connects two column rows, not
two table boxes.

- Stack: Python 3.11 or later, `uv`, `sqlglot` for the parse, `xml.etree.ElementTree` for the XML.
- Entry point: the `ddl-to-drawio` command, defined in `pyproject.toml` as `ddl_to_drawio.cli:main`.
- Host requirements: `uv` on the path. The tool has one runtime dependency, `sqlglot`.
- Input: a `.sql` file or standard input. Output: a `.drawio` file or standard output.

## Agent read

If you are an AI agent, read also [README_AGENT.md](README_AGENT.md).

## Quick start

```bash
uv sync                                                  # create .venv and install the dependencies
uv run ddl-to-drawio tests/fixtures/sample_plants.sql    # writes tests/fixtures/sample_plants.drawio
```

The sample gives 4 table boxes, 18 column rows and 3 foreign-key edges. Open the `.drawio` file in
[draw.io](https://app.diagrams.net/) with File → Open.

Run the tests with `uv run pytest`. Run the code checks with `uv run ruff check .` and
`uv run mypy`.

## Command line

The command takes one input and writes one output. All arguments are optional except the input.

| Argument | Effect |
| --- | --- |
| `input` | Path to the input `.sql` file. Use `-` to read from standard input. |
| `-o`, `--output` | Path to the output `.drawio` file. Use `-` for standard output. The default is the input path with a `.drawio` extension. |
| `--schema` | Keep only the tables of this schema, for example `public`. |
| `--dialect` | Parse with this SQL dialect. The default is `postgres`. |

```bash
uv run ddl-to-drawio dump.sql -o erd.drawio     # explicit output path
cat dump.sql | uv run ddl-to-drawio - -o -      # standard input to standard output
uv run ddl-to-drawio dump.sql --schema public   # one schema only
uv run ddl-to-drawio dump.sql --dialect mysql   # a different dialect
```

The command returns `0` on success. It returns `1` and prints a message to standard error if it
cannot read the input, if the parse fails, if the DDL holds no table, or if it cannot write the
output.

## Supported DDL

The parser walks the `sqlglot` abstract syntax tree (AST). No regular expression reads the DDL.

- Dialects: `postgres` (the default), `mysql`, `trino`, `presto` and `duckdb`. Write the value in
  lower case. `--dialect mysql` is correct. `--dialect MySQL` is not.
- Statements: `CREATE TABLE` columns and types, `NOT NULL`, `PRIMARY KEY` (inline and table-level),
  and `UNIQUE`.
- Foreign keys in the three forms of a `pg_dump` file: an out-of-line
  `ALTER TABLE ONLY ... ADD CONSTRAINT ... FOREIGN KEY ... REFERENCES ...`, an inline column-level
  `REFERENCES`, and an inline table-level `FOREIGN KEY (...) REFERENCES ...`.
- Names: the tool folds an unquoted identifier to lower case, as PostgreSQL does. It keeps a quoted
  identifier as written. A table with no schema gets the default schema `public`. An
  `ALTER TABLE public.foo` therefore resolves against a `CREATE TABLE foo`.

### Limits

- The tool ignores `SET`, `CREATE INDEX`, `CHECK` constraints and comments. This is the design, not
  an error.
- The diagram shows an edge only for a `FOREIGN KEY ... REFERENCES` constraint that the DDL holds.
  Trino, Presto and DuckDB do not enforce foreign keys, so their DDL usually omits them. A diagram
  from those dialects is then tables-only. The cause is the source DDL, not the tool.
- A foreign key to a table that the dump does not hold is skipped. The tool prints a warning to
  standard error. It does not stop.
- `NOT NULL` and `UNIQUE` are parsed, but they do not appear in the diagram. See
  [README_AGENT.md — Known drift](README_AGENT.md#known-drift).

## Output

Each table becomes an `mxCell` table box with a grey (`#B8B8B8`) header band. Each column becomes a
child row, split into a bold name part and a regular-weight type part. The two parts keep the same
width in one table. A foreign-key edge connects the child column cell to the parent column cell in
crow's-foot notation. The edge stays on the correct rows after you move the table boxes in draw.io.

The layout is a deterministic grid. The tool sizes each box from the number of columns and the
length of the labels. The result opens without overlaps. For a better arrangement, open the file in
draw.io and select **Arrange → Layout → Organic**.

The exact style string of each cell is a contract. See
[README_AGENT.md — draw.io cell contract](README_AGENT.md#drawio-cell-contract).

## Layout

```
tool-sql-to-drawio/
├── README.md                    # this file: what the tool is and how to run it
├── README_AGENT.md              # module map, code contracts, known drift
├── claude_interaction_steps.md  # branch-by-branch history of the agent sessions
├── pyproject.toml               # project metadata, the ddl-to-drawio script, ruff and mypy
├── uv.lock
├── .python-version
├── src/ddl_to_drawio/
│   ├── __init__.py
│   ├── cli.py                   # argument parsing, input, output, exit code
│   ├── model.py                 # the dataclasses TableId, Column, Table, ForeignKey, Schema
│   ├── parser.py                # sqlglot AST to model
│   ├── layout.py                # box position and box size
│   └── emitter.py               # model to draw.io XML
└── tests/
    ├── test_parser.py
    ├── test_emitter.py
    ├── test_cli.py
    └── fixtures/
        ├── sample_plants.sql    # 4 tables, PostgreSQL, 3 foreign keys
        └── sample_mysql.sql     # 4 tables, MySQL
```
