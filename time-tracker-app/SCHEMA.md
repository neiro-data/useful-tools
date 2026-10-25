# SCHEMA.md

The SQLite data model of this project. Referenced from [README.md](README.md).

The canonical DDL lives in `app/db_schema.py`, together with the indexes and the idempotent
initialization and migrations. The diagram below is a view of that file. Update both together.

The database holds six tables.

```mermaid
erDiagram
    categories ||--o{ entries : "categorizes"
    entries    ||--o{ entry_tags : "tagged by"
    tags       ||--o{ entry_tags : "applied to"

    categories {
        INTEGER id PK
        TEXT    name UK "NOT NULL, unique - also the seed match key"
        TEXT    color "nullable, hex or CSS name, max 32 chars"
        INTEGER is_active "NOT NULL, default 1 - UI-owned, never seeded"
        INTEGER sort_order "NOT NULL, default 0 - spaced in gaps of 10"
    }

    tags {
        INTEGER id PK
        TEXT    name UK "NOT NULL, unique - created on first use"
        INTEGER is_active "NOT NULL, default 1"
    }

    entries {
        INTEGER id PK
        TEXT    title "NOT NULL"
        TEXT    notes "nullable"
        INTEGER category_id FK "NOT NULL, ON DELETE RESTRICT"
        TEXT    start_ts "NOT NULL, ISO-8601 UTC"
        TEXT    end_ts "nullable - NULL while a timer is running"
        REAL    duration_minutes "nullable until the entry is closed"
        TEXT    entry_mode "NOT NULL, CHECK in (timer, manual)"
        TEXT    created_at "NOT NULL, ISO-8601 UTC"
        TEXT    updated_at "NOT NULL, ISO-8601 UTC"
    }

    entry_tags {
        INTEGER entry_id PK,FK "ON DELETE CASCADE"
        INTEGER tag_id PK,FK "ON DELETE CASCADE"
    }

    report_exports {
        INTEGER id PK
        TEXT    report_type "NOT NULL, CHECK in (weekly, monthly, quarterly)"
        TEXT    period_start "NOT NULL"
        TEXT    period_end "NOT NULL"
        TEXT    format "NOT NULL, CHECK in (html, csv, pdf, md)"
        TEXT    created_at "NOT NULL, ISO-8601 UTC"
        TEXT    file_path "NOT NULL"
    }

    settings {
        INTEGER id PK
        TEXT    default_entry_mode "NOT NULL, CHECK in (timer, manual)"
        TEXT    week_starts_on "NOT NULL"
        TEXT    default_export_format "NOT NULL, CHECK in (html, csv, pdf, md)"
        TEXT    database_label "NOT NULL"
        TEXT    timezone "NOT NULL - drives day boundaries"
    }
```
GitHub renders this Mermaid `erDiagram` natively. There is no image to regenerate, and the diff of
a schema change stays readable in a review.

`report_exports` and `settings` stand alone. Neither has a foreign key. `settings` holds exactly
one row, seeded on the first bootstrap by `init_db`.

## Conventions

Read these before you write a query.

- **A timestamp is ISO-8601 TEXT in UTC**, for example `2026-07-13T14:30:00+00:00`. It sorts
  lexicographically in the same order as chronologically, and it survives a CSV or JSON round
  trip. A caller normalizes to UTC on write, and localizes on display with `settings.timezone`.
- **A boolean is an `INTEGER`, 0 or 1.** SQLite has no boolean type.
- **An enum-like column uses a `CHECK` constraint**, not a lookup table. The value sets are small,
  fixed, and defined by the application. A user cannot edit them.
- **Foreign keys are enforced, but only per connection.** Every connection of the application sets
  `PRAGMA foreign_keys = ON`. SQLite defaults it off. An ad-hoc `sqlite3` shell session does not
  get it. Set it yourself before you change any data.

## Indexes

These are the indexes beyond the implicit primary keys and the `UNIQUE` constraints.

| Index | Columns | Serves |
| --- | --- | --- |
| `idx_entries_start_ts` | `entries (start_ts)` | The date-range scans. This is the hottest pattern: Today, Week, Month and Reports. |
| `idx_entries_category_id` | `entries (category_id)` | Filtering time by category, and the foreign-key lookup. |
| `idx_entry_tags_tag_id` | `entry_tags (tag_id)` | The reverse join: every entry with one tag. |

The primary key of `entry_tags` is `(entry_id, tag_id)`. It already indexes `entry_id` first. Only
the reverse direction therefore needs an explicit index.

## Seed data

`seed/categories.toml` holds the categories. `app/seed.py` applies them. The seeding is opt-in: no
category is written on start. `categories.name` is the match key of the seed.

`categories.is_active` and `categories.sort_order` are owned by the interface. The seed never
writes them. `sort_order` is spaced in gaps of 10, so a new category fits between two others
without a renumbering.
