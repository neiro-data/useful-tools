# test_reports

Sample report output generated from the **dummy database** (`dummy.db`, branded
`DUMMY DATA (app.dummy_data)`), never from the real `time_tracker.db`. These files exist so the
report/export formats can be eyeballed and diffed without re-running the whole pipeline by hand.

## How the data was generated

```bash
uv run python -m app.dummy_data --days 240 --reset
```

Deterministic (default seed `20260713`): 690 completed entries spanning **2025-11-27 → 2026-07-24**,
weekends skipped, spread over the 5 categories already defined in `seed/categories.toml`
(`Learning`, `Meetings - Org`, `Meetings - Technical`, `Organizational`, `Technical`) and the
8 generator tags. No new categories were introduced.

## How the reports were generated

```bash
TIME_TRACKER_DATABASE_PATH=$PWD/dummy.db uv run uvicorn app.main:app --port 8123
```

Every file uses the same anchor date, **`2026-06-15`**, chosen so all three periods fall inside
fully-populated history:

| Period    | Resolved range            | Entries | Total     |
| --------- | ------------------------- | ------: | --------- |
| `week`    | 2026-06-15 → 2026-06-21   |      20 | 23h 0m    |
| `month`   | 2026-06-01 → 2026-06-30   |      89 | 110h 30m  |
| `quarter` | 2026-04-01 → 2026-06-30   |     265 | 336h 45m  |

## Files — one case per period × format

| File                      | Endpoint                                                        |
| ------------------------- | --------------------------------------------------------------- |
| `<period>-summary.json`   | `GET /reports/summary?period=<period>&date=2026-06-15`            |
| `<period>-narrative.json` | `GET /reports/narrative?period=<period>&date=2026-06-15`          |
| `<period>-report.html`    | `GET /exports/report.html?period=<period>&date=2026-06-15`        |
| `<period>-entries.csv`    | `GET /exports/entries.csv?start_date=…&end_date=…`                |

`/exports/entries.csv` takes an explicit date range rather than a `period`, so each CSV was
requested with the `start_date`/`end_date` that the matching `summary.json` resolved to — which is
also the cross-check: CSV row count equals that period's `entry_count` (20 / 89 / 265).

The fifth export endpoint, `GET /exports/backup`, is not represented here: it returns a full
SQLite snapshot rather than a report, and its output is `dummy.db` itself.

## Regenerating

Re-run the two commands above, then re-issue the requests in the table. Because generation is
seeded and the anchor date is fixed, the output is reproducible — but note the period *bounds* are
absolute dates, so they do not drift with "today".
