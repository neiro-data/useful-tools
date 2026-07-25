"""Generate a throwaway database full of realistic-looking data, for tests and experiments.

Why this exists
---------------
The automated test suite already isolates itself (``tests/conftest.py`` points
``TIME_TRACKER_DATABASE_PATH`` at a ``tmp_path`` file per test). This module covers the *other*
case: poking at the app by hand -- curling endpoints, opening the SPA to see how a screen looks
with real volume, trying a migration, exploring the schema in the ``sqlite3`` shell. Those all go
through whatever ``TIME_TRACKER_DATABASE_PATH`` currently points at, which by default is the real
``time_tracker.db``. This gives you a populated, disposable database to point at instead.

The generated file is git-ignored (``.gitignore`` ignores ``*.db``, and ``dummy.db`` is listed
explicitly so its purpose is obvious). It is data, not a fixture to commit -- regenerate it rather
than sharing it.

Safety
------
The whole point is to *not* touch the real database, so the guard cannot rely on the filename.
Instead the generated database is branded: ``settings.database_label`` is set to
:data:`DUMMY_DATABASE_LABEL`. Before writing to (or deleting) an existing file, this module reads
that label back and refuses unless it matches. A real time-tracker database is labelled with the
app name, so it is rejected -- even if you pass ``--path time_tracker.db`` by accident. Anything
that is not a time-tracker database at all is rejected too.

Determinism
-----------
Generation is seeded (``--seed``, default 20260713), so the same arguments always produce the same
database. That makes "it looked like this yesterday" reproducible and keeps screenshots stable.
"""

import argparse
import random
import sqlite3
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.db_schema import init_db
from app.seed import DEFAULT_SEED_PATH, SeedError, load_seed_file, sync_categories

#: Written to ``settings.database_label`` and checked before every destructive operation.
DUMMY_DATABASE_LABEL = "DUMMY DATA (app.dummy_data)"

DEFAULT_DUMMY_PATH = Path(__file__).resolve().parent.parent / "dummy.db"
DEFAULT_DAYS = 28
DEFAULT_SEED = 20260713

#: Tags the generator draws from. Created on demand, like the real app does on first use.
_TAGS = (
    "deep-work",
    "review",
    "planning",
    "support",
    "recruiting",
    "docs",
    "on-call",
    "pairing",
)

#: Entry titles per category name, matching ``seed/categories.toml``. Categories not listed here
#: (e.g. one you added to the seed file) fall back to :data:`_FALLBACK_TITLES`.
_TITLES_BY_CATEGORY: dict[str, tuple[str, ...]] = {
    "Meetings - Org": (
        "Weekly team sync",
        "1:1 with manager",
        "Sprint planning",
        "Quarterly roadmap review",
        "All-hands",
    ),
    "Meetings - Technical": (
        "Architecture review",
        "Incident post-mortem",
        "Design walkthrough",
        "API contract discussion",
        "Backlog grooming",
    ),
    "Organizational": (
        "Inbox and triage",
        "Expense reports",
        "Interview debrief notes",
        "Quarterly goal write-up",
        "Onboarding checklist",
    ),
    "Technical": (
        "Fix report export encoding",
        "Refactor entries repository",
        "Investigate slow week query",
        "Add index for tag lookups",
        "Wire up settings screen",
        "Chase down flaky timer test",
    ),
    "Learning": (
        "SQLite internals reading",
        "FastAPI dependency deep-dive",
        "Polars tutorial",
        "Conference talk: query planners",
        "Type-checking workshop",
    ),
}

_FALLBACK_TITLES = (
    "Focused work block",
    "Follow-ups",
    "Ad-hoc task",
)


class DummyDataError(Exception):
    """Raised when the target database is missing, unreadable, or not a dummy database."""


@dataclass(frozen=True)
class GenerationResult:
    """Counts of what :func:`generate` wrote."""

    path: Path
    categories: int
    tags: int
    entries: int
    running_timer: bool

    def summary(self) -> str:
        """Human-readable one-liner."""
        timer = ", 1 running timer" if self.running_timer else ""
        return f"{self.categories} categories, {self.tags} tags, {self.entries} entries{timer}"


def _iso(moment: datetime) -> str:
    """Format a datetime the way the schema stores it: ISO-8601, UTC, offset included."""
    return moment.astimezone(UTC).isoformat()


def _connect(path: Path) -> sqlite3.Connection:
    """Open a connection to an explicit path (not the configured one) with FKs enforced."""
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def read_database_label(path: Path) -> str | None:
    """Return the ``settings.database_label`` of an existing database file.

    Returns ``None`` if the file does not exist, is empty, has no ``settings`` table, or has no
    settings row -- i.e. "nothing here that we would be destroying".

    Raises:
        DummyDataError: if the file exists but cannot be opened as a SQLite database.
    """
    if not path.exists() or path.stat().st_size == 0:
        return None

    try:
        conn = _connect(path)
    except sqlite3.Error as exc:  # pragma: no cover - defensive
        raise DummyDataError(f"{path} could not be opened as a SQLite database: {exc}") from exc

    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'settings'"
        ).fetchone()
        if row is None:
            raise DummyDataError(
                f"{path} exists but is not a time-tracker database (no `settings` table). "
                "Refusing to touch it."
            )
        settings_row = conn.execute("SELECT database_label FROM settings LIMIT 1").fetchone()
    except sqlite3.DatabaseError as exc:
        raise DummyDataError(f"{path} is not a readable SQLite database: {exc}") from exc
    finally:
        conn.close()

    if settings_row is None:
        return None
    label: str = settings_row["database_label"]
    return label


def assert_safe_target(path: Path) -> None:
    """Refuse to write to anything that is not an empty path or an existing dummy database.

    Raises:
        DummyDataError: if ``path`` holds a database that this module did not generate.
    """
    label = read_database_label(path)
    if label is None or label == DUMMY_DATABASE_LABEL:
        return
    raise DummyDataError(
        f"{path} is a real time-tracker database (database_label={label!r}), not a dummy one. "
        "Refusing to overwrite it. Pick a different --path."
    )


def _clear_generated_data(conn: sqlite3.Connection) -> None:
    """Wipe entries and tags so a re-run replaces the data instead of stacking onto it.

    Categories are left alone: they are re-synced from ``seed/categories.toml`` and deleting them
    would trip the ``ON DELETE RESTRICT`` on ``entries.category_id`` anyway.
    """
    with conn:
        conn.execute("DELETE FROM entry_tags")
        conn.execute("DELETE FROM entries")
        conn.execute("DELETE FROM tags")


def _brand_as_dummy(conn: sqlite3.Connection) -> None:
    """Stamp the settings row with the dummy label, so :func:`assert_safe_target` recognizes it."""
    with conn:
        conn.execute("UPDATE settings SET database_label = ?", (DUMMY_DATABASE_LABEL,))


def _insert_tags(conn: sqlite3.Connection) -> dict[str, int]:
    """Insert :data:`_TAGS` and return a name -> id map."""
    with conn:
        conn.executemany(
            "INSERT INTO tags (name, is_active) VALUES (?, 1)", [(name,) for name in _TAGS]
        )
    return {row["name"]: row["id"] for row in conn.execute("SELECT id, name FROM tags")}


def _titles_for(category_name: str) -> tuple[str, ...]:
    return _TITLES_BY_CATEGORY.get(category_name, _FALLBACK_TITLES)


def _day_entries(
    day: datetime,
    categories: list[sqlite3.Row],
    rng: random.Random,
) -> list[tuple[str, int, datetime, datetime]]:
    """Build one weekday's worth of (title, category_id, start, end) tuples.

    The day starts at 09:00 UTC and entries run back to back with small gaps, so durations sum to
    something believable (roughly 4-7 hours) rather than overlapping or spanning midnight.
    """
    entries: list[tuple[str, int, datetime, datetime]] = []
    cursor = day.replace(hour=9, minute=0, second=0, microsecond=0)

    for _ in range(rng.randint(3, 5)):
        category = rng.choice(categories)
        title = rng.choice(_titles_for(category["name"]))
        # Durations land on quarter-hours, the way a human logs them.
        duration = timedelta(minutes=15 * rng.randint(2, 8))
        end = cursor + duration
        entries.append((title, int(category["id"]), cursor, end))
        # A gap between blocks: coffee, context switch, or an untracked interruption.
        cursor = end + timedelta(minutes=15 * rng.randint(0, 4))

    return entries


def _insert_entries(
    conn: sqlite3.Connection,
    categories: list[sqlite3.Row],
    tag_ids: dict[str, int],
    *,
    days: int,
    rng: random.Random,
    now: datetime,
) -> int:
    """Generate ``days`` days of finished entries ending yesterday. Returns the count written."""
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    written = 0

    with conn:
        for offset in range(days, 0, -1):
            day = today - timedelta(days=offset)
            if day.weekday() >= 5:  # Saturday/Sunday: no logged work.
                continue

            for title, category_id, start, end in _day_entries(day, categories, rng):
                duration_minutes = (end - start).total_seconds() / 60
                cursor = conn.execute(
                    """
                    INSERT INTO entries (
                        title, notes, category_id, start_ts, end_ts, duration_minutes,
                        entry_mode, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        title,
                        None,
                        category_id,
                        _iso(start),
                        _iso(end),
                        duration_minutes,
                        "manual" if rng.random() < 0.4 else "timer",
                        _iso(end),
                        _iso(end),
                    ),
                )
                entry_id = cursor.lastrowid
                for tag_name in rng.sample(sorted(tag_ids), rng.randint(0, 2)):
                    conn.execute(
                        "INSERT INTO entry_tags (entry_id, tag_id) VALUES (?, ?)",
                        (entry_id, tag_ids[tag_name]),
                    )
                written += 1

    return written


def _insert_running_timer(
    conn: sqlite3.Connection,
    categories: list[sqlite3.Row],
    rng: random.Random,
    now: datetime,
) -> None:
    """Insert one open entry (``end_ts IS NULL``), started 37 minutes ago.

    Useful for eyeballing the Today screen's live timer without waiting for one to accumulate.
    """
    category = rng.choice(categories)
    start = now - timedelta(minutes=37)
    with conn:
        conn.execute(
            """
            INSERT INTO entries (
                title, notes, category_id, start_ts, end_ts, duration_minutes,
                entry_mode, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, NULL, NULL, 'timer', ?, ?)
            """,
            (
                rng.choice(_titles_for(category["name"])),
                None,
                int(category["id"]),
                _iso(start),
                _iso(start),
                _iso(start),
            ),
        )


def generate(
    path: Path = DEFAULT_DUMMY_PATH,
    *,
    days: int = DEFAULT_DAYS,
    seed: int = DEFAULT_SEED,
    running_timer: bool = False,
    seed_file: Path = DEFAULT_SEED_PATH,
    now: datetime | None = None,
) -> GenerationResult:
    """Build (or rebuild) a dummy database at ``path`` and return what was written.

    Safe to re-run: existing entries and tags are cleared first, so the result depends only on the
    arguments, not on how many times this has been called.

    Args:
        path: Where to write. Must not be an existing real database -- see
            :func:`assert_safe_target`.
        days: How many days back to generate. Weekends are skipped.
        seed: RNG seed -- same seed and arguments produce the same database.
        running_timer: Also leave one open entry, as if a timer were running right now.
        seed_file: Category seed TOML to populate categories from.
        now: Override "now" (used by tests); defaults to the current UTC time.

    Raises:
        DummyDataError: if the target is a real database, or the seed file is unusable.
    """
    assert_safe_target(path)
    # random, not secrets: this is sample data, and reproducibility is the point.
    rng = random.Random(seed)  # noqa: S311
    now = now or datetime.now(UTC)

    try:
        categories_from_file = load_seed_file(seed_file)
    except SeedError as exc:
        raise DummyDataError(str(exc)) from exc

    path.parent.mkdir(parents=True, exist_ok=True)
    conn = _connect(path)
    try:
        init_db(conn)
        _brand_as_dummy(conn)
        _clear_generated_data(conn)
        sync_categories(conn, categories_from_file)

        categories = list(conn.execute("SELECT id, name FROM categories WHERE is_active = 1"))
        if not categories:
            raise DummyDataError(f"{seed_file} produced no active categories to attach entries to.")

        tag_ids = _insert_tags(conn)
        entries = _insert_entries(conn, categories, tag_ids, days=days, rng=rng, now=now)
        if running_timer:
            _insert_running_timer(conn, categories, rng, now)
            entries += 1

        return GenerationResult(
            path=path,
            categories=len(categories),
            tags=len(tag_ids),
            entries=entries,
            running_timer=running_timer,
        )
    finally:
        conn.close()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.dummy_data",
        description="Generate a disposable, git-ignored database populated with sample data.",
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=DEFAULT_DUMMY_PATH,
        help=f"Where to write the dummy database (default: {DEFAULT_DUMMY_PATH.name}).",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_DAYS,
        help=f"How many days back to generate; weekends are skipped (default: {DEFAULT_DAYS}).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"RNG seed, for reproducible output (default: {DEFAULT_SEED}).",
    )
    parser.add_argument(
        "--running-timer",
        action="store_true",
        help="Also leave one entry open, as if a timer were running right now.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete the dummy database file first, instead of rewriting its contents.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entrypoint for ``uv run python -m app.dummy_data``. Returns a process exit code."""
    args = _build_parser().parse_args(argv)
    path: Path = args.path

    try:
        if args.reset:
            assert_safe_target(path)
            path.unlink(missing_ok=True)
        result = generate(
            path,
            days=args.days,
            seed=args.seed,
            running_timer=args.running_timer,
        )
    except DummyDataError as exc:
        print(f"error: {exc}", file=sys.stderr)  # noqa: T201
        return 1

    print(f"wrote {result.path}: {result.summary()}")  # noqa: T201
    print(  # noqa: T201
        "point the app at it with:\n"
        f"  TIME_TRACKER_DATABASE_PATH={result.path} uv run uvicorn app.main:app --reload"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
