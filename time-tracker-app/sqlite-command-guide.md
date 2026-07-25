# SQLite Command Guide

A practical reference for the `sqlite3` CLI and the SQL dialect it speaks. Dot-commands (`.foo`) are
CLI features, not SQL — they take no trailing semicolon and only work inside the `sqlite3` shell.

Tested against SQLite 3.40+. A few items are flagged where they need a newer version.

---

## 1. Opening and quitting

```bash
sqlite3 mydata.db            # open (creates the file lazily, on first write)
sqlite3                      # transient in-memory database, discarded on exit
sqlite3 :memory:             # same, explicit
sqlite3 mydata.db -readonly  # open read-only (safe for poking at a live DB)
```

Inside the shell:

```
.quit            -- or .exit, or Ctrl-D
.help            -- list every dot-command
.help backup     -- help for one dot-command
```

Run SQL without entering the shell — handy in scripts and pipelines:

```bash
sqlite3 mydata.db "SELECT count(*) FROM entries;"
sqlite3 mydata.db < script.sql
echo "SELECT 1;" | sqlite3 mydata.db
sqlite3 mydata.db ".schema entries"         # dot-commands work as arguments too
```

---

## 2. Inspecting a database

```
.databases                 -- attached databases and their file paths
.tables                    -- list tables (and views)
.tables 'user%'            -- filter by LIKE pattern
.schema                    -- CREATE statements for everything
.schema entries            -- ...for one table
.schema --indent           -- pretty-printed
.fullschema --indent       -- schema + ANALYZE stats
.indexes entries           -- indexes on a table
.dbinfo                    -- page size, encoding, page count, etc.
```

Same information via SQL (works from any client, not just the CLI):

```sql
SELECT name, type FROM sqlite_master WHERE type IN ('table', 'index', 'view');
SELECT sql FROM sqlite_master WHERE name = 'entries';

PRAGMA table_info(entries);        -- columns, types, NOT NULL, default, PK position
PRAGMA foreign_key_list(entries);  -- outgoing FKs
PRAGMA index_list(entries);
PRAGMA index_info(idx_entries_started_at);
```

---

## 3. Output formatting

```
.mode box            -- unicode-boxed table; the nicest for reading
.mode table          -- ASCII table
.mode column         -- aligned columns
.mode list           -- pipe-separated (default)
.mode csv
.mode json           -- emits a JSON array of objects
.mode markdown       -- paste straight into docs
.mode insert entries -- emit INSERT INTO entries ... statements
.mode quote

.headers on
.nullvalue NULL      -- show NULLs instead of empty string
.separator ','       -- for list/csv modes
.width 20 12 0       -- fix column widths (0 = auto)
.timer on            -- wall/user/sys time per statement
.changes on          -- print rows-changed after each statement
```

A comfortable interactive default:

```
.mode box
.headers on
.timer on
.nullvalue ␀
```

Persist these in `~/.sqliterc` so every session starts that way.

Redirect output:

```
.once out.csv        -- next query's results go to the file
.output report.txt   -- all output goes to the file until...
.output              -- ...back to stdout
.once -e             -- open results in $EDITOR
```

---

## 4. Import and export

```
.import --csv data.csv mytable       -- appends; creates the table if it doesn't exist
.import --csv --skip 1 data.csv mytable
.import --csv /dev/stdin mytable     -- from a pipe
```

Export a query to CSV:

```bash
sqlite3 -header -csv mydata.db "SELECT * FROM entries;" > entries.csv
```

Or in-shell:

```
.headers on
.mode csv
.once entries.csv
SELECT * FROM entries;
```

Dump to SQL text (portable, diffable, good for version control of small DBs):

```
.dump                 -- whole database as SQL
.dump entries         -- one table
.output backup.sql
.dump
.output
```

Restore: `sqlite3 new.db < backup.sql`

---

## 5. Schema DDL

```sql
CREATE TABLE IF NOT EXISTS categories (
    id          INTEGER PRIMARY KEY,          -- alias for ROWID; autoincrements naturally
    name        TEXT    NOT NULL UNIQUE,
    color       TEXT    NOT NULL DEFAULT '#888888',
    archived    INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0, 1)),
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE entries (
    id           INTEGER PRIMARY KEY,
    category_id  INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    started_at   TEXT    NOT NULL,
    ended_at     TEXT,
    note         TEXT,
    CHECK (ended_at IS NULL OR ended_at >= started_at)
);
```

Notes that bite people:

- **Type affinity, not enforcement.** A `TEXT` column will happily store an integer. Use `CHECK`
  constraints, or `STRICT` tables (3.37+) for real type enforcement:
  `CREATE TABLE t (...) STRICT;`
- **Foreign keys are off by default per connection.** Enable them every time:
  `PRAGMA foreign_keys = ON;`
- `INTEGER PRIMARY KEY` is the row id and is the fastest key. `AUTOINCREMENT` adds overhead and is
  rarely needed — it only guarantees ids are never reused.
- There are no native `BOOLEAN`, `DATE`, or `DATETIME` types. Use `INTEGER` 0/1 and ISO-8601 `TEXT`
  (`'2026-07-25T14:03:00Z'`), which sorts and compares correctly as a string.

Altering tables (limited, but enough for most migrations):

```sql
ALTER TABLE entries ADD COLUMN billable INTEGER NOT NULL DEFAULT 0;
ALTER TABLE entries RENAME TO time_entries;
ALTER TABLE entries RENAME COLUMN note TO description;   -- 3.25+
ALTER TABLE entries DROP COLUMN description;             -- 3.35+
```

Anything else (changing a type, adding a constraint) needs the 12-step dance: create a new table,
`INSERT INTO new SELECT ... FROM old`, drop the old, rename. Do it inside a transaction with
`PRAGMA foreign_keys = OFF;` around it.

Views, indexes, triggers:

```sql
CREATE INDEX idx_entries_started ON entries(started_at);
CREATE INDEX idx_entries_cat_started ON entries(category_id, started_at);
CREATE UNIQUE INDEX idx_cat_name ON categories(name);
CREATE INDEX idx_entries_open ON entries(started_at) WHERE ended_at IS NULL;  -- partial

CREATE VIEW open_entries AS
    SELECT * FROM entries WHERE ended_at IS NULL;

CREATE TRIGGER entries_touch AFTER UPDATE ON entries
BEGIN
    UPDATE entries SET updated_at = datetime('now') WHERE id = NEW.id;
END;

DROP INDEX IF EXISTS idx_entries_started;
```

---

## 6. Everyday DML

```sql
INSERT INTO categories (name, color) VALUES ('Deep work', '#3366cc');
INSERT INTO categories (name, color) VALUES ('A', '#111'), ('B', '#222');   -- multi-row

-- upsert (3.24+)
INSERT INTO categories (name, color) VALUES ('Deep work', '#000000')
ON CONFLICT(name) DO UPDATE SET color = excluded.color;

INSERT INTO categories (name, color) VALUES ('Deep work', '#000')
ON CONFLICT DO NOTHING;

INSERT OR REPLACE INTO categories (id, name, color) VALUES (1, 'Deep work', '#000');
INSERT OR IGNORE  INTO categories (name) VALUES ('Deep work');

UPDATE entries SET ended_at = datetime('now') WHERE ended_at IS NULL;

DELETE FROM entries WHERE started_at < '2025-01-01';

-- RETURNING (3.35+): get back what you just wrote
INSERT INTO categories (name) VALUES ('New') RETURNING id, name;
DELETE FROM entries WHERE id = 7 RETURNING *;

SELECT last_insert_rowid();
SELECT changes();          -- rows affected by the last statement
```

---

## 7. Querying: the useful bits

```sql
-- Common table expressions
WITH daily AS (
    SELECT date(started_at)                                   AS day,
           sum(strftime('%s', ended_at) - strftime('%s', started_at)) AS seconds
    FROM entries
    WHERE ended_at IS NOT NULL
    GROUP BY day
)
SELECT day, seconds / 3600.0 AS hours
FROM daily
ORDER BY day DESC
LIMIT 30;

-- Window functions (3.25+)
SELECT day,
       seconds,
       sum(seconds) OVER (ORDER BY day)                        AS running_total,
       avg(seconds) OVER (ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS avg_7d,
       rank()       OVER (ORDER BY seconds DESC)               AS rk
FROM daily;

-- Recursive CTE: generate a date series (fills gaps in reports)
WITH RECURSIVE days(d) AS (
    SELECT date('now', '-29 days')
    UNION ALL
    SELECT date(d, '+1 day') FROM days WHERE d < date('now')
)
SELECT d FROM days;

-- Conditional aggregation
SELECT category_id,
       count(*)                                     AS n,
       sum(CASE WHEN ended_at IS NULL THEN 1 ELSE 0 END) AS still_open
FROM entries GROUP BY category_id;

-- String aggregation
SELECT category_id, group_concat(note, ' | ') FROM entries GROUP BY category_id;
```

Handy scalar functions: `coalesce`, `nullif`, `ifnull`, `iif(cond, a, b)` (3.32+), `length`, `substr`,
`replace`, `trim`, `upper`/`lower`, `instr`, `printf('%.2f', x)`, `round`, `abs`, `cast(x AS INTEGER)`,
`random`, `hex(randomblob(16))` for ids.

---

## 8. Dates and times

SQLite stores no date type; these functions operate on ISO-8601 text, Unix epochs, or Julian days.

```sql
SELECT date('now'), time('now'), datetime('now');          -- UTC
SELECT datetime('now', 'localtime');
SELECT datetime('now', 'start of month', '+1 month', '-1 day');   -- last day of month
SELECT date('now', 'weekday 0', '-6 days');                -- Monday of this week
SELECT strftime('%Y-%W', started_at)      AS iso_week FROM entries;
SELECT strftime('%s', 'now');                              -- epoch seconds (as text)
SELECT datetime(1753440000, 'unixepoch');                  -- epoch -> timestamp
SELECT julianday('now') - julianday(started_at) AS days_ago FROM entries;
```

Duration between two timestamps, in seconds:

```sql
SELECT strftime('%s', ended_at) - strftime('%s', started_at) AS secs FROM entries;
```

Common `strftime` codes: `%Y %m %d %H %M %S %j` (day of year) `%W` (week) `%w` (weekday, 0=Sunday)
`%s` (epoch).

---

## 9. JSON

Built in since 3.38 (earlier, via the `json1` extension).

```sql
SELECT json_extract('{"a":{"b":42}}', '$.a.b');       -- 42
SELECT '{"a":{"b":42}}' -> '$.a' AS json_val,         -- 3.38+: -> returns JSON
       '{"a":{"b":42}}' ->> '$.a.b' AS sql_val;       -- ->> returns a SQL scalar

SELECT json_object('id', id, 'name', name) FROM categories;
SELECT json_group_array(json_object('id', id, 'name', name)) FROM categories;

SELECT value FROM json_each('[1,2,3]');               -- table-valued: one row per element
SELECT key, value FROM json_each('{"a":1,"b":2}');

UPDATE settings SET blob = json_set(blob, '$.theme', 'dark') WHERE id = 1;
SELECT json_valid(blob) FROM settings;

-- index a JSON field via a generated column
ALTER TABLE settings ADD COLUMN theme TEXT
    GENERATED ALWAYS AS (blob ->> '$.theme') VIRTUAL;
CREATE INDEX idx_settings_theme ON settings(theme);
```

---

## 10. Transactions

```sql
BEGIN;                      -- deferred
BEGIN IMMEDIATE;            -- take the write lock now; avoids surprise SQLITE_BUSY mid-transaction
COMMIT;
ROLLBACK;

SAVEPOINT s1;
ROLLBACK TO s1;
RELEASE s1;
```

Bulk loads are dramatically faster inside one transaction — each bare `INSERT` otherwise gets its own
commit and `fsync`.

---

## 11. Performance

```sql
EXPLAIN QUERY PLAN
SELECT * FROM entries WHERE category_id = 3 ORDER BY started_at;
```

Read the output for `SCAN` (full table scan — usually the problem) vs `SEARCH ... USING INDEX ...`
(good). `USE TEMP B-TREE FOR ORDER BY` means the sort isn't index-backed.

```sql
ANALYZE;                    -- refresh the query planner's statistics; do it after bulk loads
```

Pragmas worth setting on a connection:

```sql
PRAGMA journal_mode = WAL;      -- persistent; concurrent readers alongside one writer
PRAGMA synchronous = NORMAL;    -- sensible with WAL; FULL is the durable-but-slow default
PRAGMA foreign_keys = ON;       -- per-connection, must be set every time
PRAGMA busy_timeout = 5000;     -- ms to wait on a locked DB instead of failing instantly
PRAGMA cache_size = -64000;     -- negative = KiB, so this is 64 MB
PRAGMA temp_store = MEMORY;
```

Rules of thumb: index the columns you filter and join on; a composite index `(a, b)` also serves
queries on `a` alone but not on `b` alone; covering indexes (all selected columns in the index) avoid
touching the table; too many indexes slow writes.

Reclaim space after large deletes:

```sql
VACUUM;                             -- rebuilds the file; needs free disk space ~2x the DB
PRAGMA auto_vacuum = INCREMENTAL;   -- must be set before the DB has tables
PRAGMA incremental_vacuum;
```

---

## 12. Backup and integrity

```
.backup backup.db            -- safe online backup, even with the DB in use
.restore backup.db
.clone copy.db               -- copy into a new DB, skipping corrupt pages
```

From the shell:

```bash
sqlite3 mydata.db ".backup 'backup-$(date +%F).db'"
```

Never just `cp` a database that a process might be writing — you can capture a torn state (and with
WAL you'd also need the `-wal` and `-shm` files).

Health checks:

```sql
PRAGMA integrity_check;         -- full verification; 'ok' if healthy
PRAGMA quick_check;             -- faster, less thorough
PRAGMA foreign_key_check;       -- lists rows violating FK constraints
```

---

## 13. Full-text search

```sql
CREATE VIRTUAL TABLE entries_fts USING fts5(note, content='entries', content_rowid='id');
INSERT INTO entries_fts(entries_fts) VALUES('rebuild');

SELECT e.*
FROM entries_fts f JOIN entries e ON e.id = f.rowid
WHERE entries_fts MATCH 'meeting NEAR/5 budget'
ORDER BY rank;

SELECT snippet(entries_fts, 0, '[', ']', '…', 10) FROM entries_fts WHERE entries_fts MATCH 'budget';
```

Keep the FTS index in sync with `AFTER INSERT/UPDATE/DELETE` triggers on the source table.

---

## 14. Attaching multiple databases

```sql
ATTACH DATABASE 'archive.db' AS arc;
INSERT INTO arc.entries SELECT * FROM main.entries WHERE started_at < '2025-01-01';
DELETE FROM main.entries WHERE started_at < '2025-01-01';
DETACH DATABASE arc;
```

Cross-database queries work normally; transactions span all attached databases.

---

## 15. From Python

```python
import sqlite3

con = sqlite3.connect("mydata.db")
con.row_factory = sqlite3.Row               # dict-like rows
con.execute("PRAGMA foreign_keys = ON")
con.execute("PRAGMA journal_mode = WAL")

with con:                                   # commits on success, rolls back on exception
    con.execute(
        "INSERT INTO categories (name, color) VALUES (?, ?)",
        ("Deep work", "#3366cc"),
    )
    con.executemany(
        "INSERT INTO entries (category_id, started_at) VALUES (:cat, :start)",
        [{"cat": 1, "start": "2026-07-25T09:00:00Z"}],
    )

for row in con.execute("SELECT id, name FROM categories ORDER BY name"):
    print(row["id"], row["name"])

con.close()
```

Always use `?` / `:name` placeholders — never f-strings or `%` formatting — so values are bound rather
than concatenated into SQL.

---

## 16. Miscellaneous dot-commands

```
.read setup.sql          -- execute a SQL file
.shell ls -la            -- run a shell command (also .system)
.echo on                 -- echo statements as they run
.log stderr              -- log SQLite messages
.bail on                 -- stop on first error (essential in scripts)
.excel                   -- send results to a spreadsheet app
.expert                  -- suggest indexes for the next query (experimental)
.selftest
.vfsinfo
```

For scripted use, the combination that fails loudly:

```bash
sqlite3 -bail -batch mydata.db < migration.sql
```

---

## Further reading

- Full CLI documentation: <https://sqlite.org/cli.html>
- SQL syntax reference: <https://sqlite.org/lang.html>
- Pragma reference: <https://sqlite.org/pragma.html>
- Quirks worth knowing: <https://sqlite.org/quirks.html>
