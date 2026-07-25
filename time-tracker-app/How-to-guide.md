# First-run walkthrough for the time tracker

## Steo 0 - Starting the app

Both servers are already running, but for future sessions, from `time-tracker-app/`:

```bash
# backend — http://127.0.0.1:8000
uv run uvicorn app.main:app --reload

# frontend — http://localhost:5173 (separate terminal)
cd frontend && npm run dev
```

Vite proxies `/api/*` to the backend, so you only ever open `http://localhost:5173`. Interactive API docs are at `http://127.0.0.1:8000/docs`.

## Step 1 — Define your categories

Categories are the top-level buckets (the colored chips on entries). With zero categories the picker in the timer widget will be empty, so this is the natural first move.

They live in a version-controlled file, `seed/categories.toml`, rather than being POSTed one at a time. Edit that file, then apply it:

```bash
uv run python -m app.seed --dry-run   # preview, writes nothing
uv run python -m app.seed             # apply
```

You can confirm that the categories were created by querying the `categories` tables.


**How re-running behaves.** `name` is the match key. Categories in the file but not yet in the database are inserted; ones already there have their `color` and `sort_order` updated to match the file. Nothing is ever deleted, so a category with entries attached can't be orphaned, and a category you created in the UI survives a seed run that doesn't mention it.

`sort_order` is spaced in gaps of 10 so you can slot a new category between two others without renumbering everything. Lower sorts first.

**One exception to "the file wins":** `is_active` is not synced. A category you retire with `POST /categories/{id}/deactivate` stays retired — re-seeding won't resurrect it. That's the one piece of category state the UI owns rather than the file.

You can still create categories ad hoc via `POST /categories` if you prefer; the seeder won't clobber them.

## Step 2 — Tags come for free

You do **not** need to pre-create tags. The Today page runs typed tag names through `resolveTagIds`, which creates any tag that doesn't exist yet and folds it into local state. Just type them into the timer widget and they'll be created on first use.

## Step 3 — Your first timed entry

On `/today`:

1. Type a title in the timer widget.
2. Pick a category, optionally type a tag or two.
3. Start the timer — this hits `POST /timer/start`.
4. Stop it when done, via the button or the **`S`** keyboard shortcut (global, but suppressed while focus is in an `input` or `textarea`).

Only one timer runs at a time. If one is already running when you start another, the backend returns a `timer_already_running` error and the page shows a conflict banner offering "Stop it and start this instead" — that's expected behavior, not a bug.

## Step 4 — Log something already finished

The same widget has a manual-add path (`POST /entries` with explicit `start_ts`/`end_ts`), for work you did before opening the app. Use this to backfill a couple of entries so the Week/Month/Reports screens have something to render.

## Step 5 — Look at the rollups

- `/week` and `/month` — grouped views over ranges
- `/reports` — `GET /reports/summary` plus a generated `/reports/narrative`

These will look empty or degenerate until a few entries exist across different days, which is why Step 4 is worth doing on day one.

## Step 6 — Exports and backup

Three endpoints exist: `/exports/entries.csv`, `/exports/report.html`, and `/exports/backup`. Worth exercising `/exports/backup` early so you know your escape hatch works before you have data you care about.

## Settings worth reviewing first

Your current settings row: `default_entry_mode=timer`, `week_starts_on=monday`, `default_export_format=md`, `database_label="Time Tracker"`, **`timezone=UTC`**.

That timezone is the one I'd check before logging real data. If you're not actually on UTC, verify how `/today` buckets entries into "today" — entries created late in the evening could land on the wrong calendar day. Confirm with one late-evening test entry rather than assuming either way.

## Data location

The SQLite file is `time-tracker-app/time_tracker.db` (currently 1 entry, 4 categories, 0 tags). It's the whole database — copying that file is a complete backup.

Note that the database itself is *not* in version control, but `seed/categories.toml` is. On a fresh machine, `uv run python -m app.seed` rebuilds your category taxonomy from scratch (it bootstraps the schema first, so it works even with no database file present).