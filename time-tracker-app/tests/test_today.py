"""Tests for the ``/today`` aggregation endpoint."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.db import get_connection
from tests._time_helpers import freeze_module_now


def test_today_is_empty_when_no_data(client: TestClient) -> None:
    response = client.get("/today")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "entries": [],
        "running_timer": None,
        "recent_categories": [],
        "recent_tags": [],
    }


def test_today_includes_todays_entries_and_excludes_running_timer(client: TestClient) -> None:
    today = datetime.now(UTC).date().isoformat()
    todays_entry = client.post(
        "/entries",
        json={
            "title": "Today entry",
            "start_ts": f"{today}T08:00:00+00:00",
            "end_ts": f"{today}T09:00:00+00:00",
        },
    ).json()
    client.post(
        "/entries",
        json={
            "title": "Old entry",
            "start_ts": "2020-01-01T08:00:00+00:00",
            "end_ts": "2020-01-01T09:00:00+00:00",
        },
    )
    running = client.post("/timer/start", json={"title": "Running now"}).json()

    response = client.get("/today")

    assert response.status_code == 200
    body = response.json()
    entry_ids = {item["id"] for item in body["entries"]}
    assert entry_ids == {todays_entry["id"]}
    assert body["running_timer"]["id"] == running["id"]


def test_today_recent_categories_and_tags(client: TestClient) -> None:
    category = client.post("/categories", json={"name": "Deep Work"}).json()
    tag = client.post("/tags", json={"name": "focus"}).json()
    today = datetime.now(UTC).date().isoformat()
    client.post(
        "/entries",
        json={
            "title": "Today entry",
            "category_id": category["id"],
            "tag_ids": [tag["id"]],
            "start_ts": f"{today}T08:00:00+00:00",
            "end_ts": f"{today}T09:00:00+00:00",
        },
    )

    response = client.get("/today")

    body = response.json()
    assert [c["id"] for c in body["recent_categories"]] == [category["id"]]
    assert [t["id"] for t in body["recent_tags"]] == [tag["id"]]


def _set_timezone(timezone: str) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE settings SET timezone = ?", (timezone,))
        conn.commit()


def test_today_day_boundary_resolves_against_configured_timezone(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An entry just after UTC midnight can belong to the *previous* local day (or vice versa) —
    the ``/today`` boundary must be computed in ``settings.timezone``, not naive UTC calendar
    days. "Now" is frozen (not asserted against wall-clock) so the test is deterministic.
    """
    frozen_now = datetime(2026, 7, 14, 2, 0, 0, tzinfo=UTC)
    freeze_module_now(monkeypatch, "app.routers.today.datetime", frozen_now)

    # Entry starts at 23:00 UTC on July 13th.
    entry = client.post(
        "/entries",
        json={
            "title": "Late shift",
            "start_ts": "2026-07-13T23:00:00+00:00",
            "end_ts": "2026-07-13T23:30:00+00:00",
        },
    ).json()

    # Default seeded timezone is UTC: "today" (frozen now = July 14th UTC) starts at
    # 2026-07-14T00:00:00Z, so the July 13th 23:00Z entry falls *outside* today's window.
    utc_response = client.get("/today")
    assert utc_response.status_code == 200
    assert entry["id"] not in {item["id"] for item in utc_response.json()["entries"]}

    # Switch to a UTC+12 timezone: local "today" (frozen now = July 14th 14:00 local) starts at
    # 2026-07-13T12:00:00Z, so the same entry now falls *inside* today's local-day window.
    _set_timezone("Pacific/Auckland")
    auckland_response = client.get("/today")
    assert auckland_response.status_code == 200
    assert entry["id"] in {item["id"] for item in auckland_response.json()["entries"]}
