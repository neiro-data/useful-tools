"""End-to-end lifecycle test exercising a realistic Phase 1 flow across every router in one pass:

categories/tags setup -> start timer -> read the running timer -> stop it (assigning
title/category/tags) -> verify the stopped entry persisted correctly -> add a manual entry ->
confirm ``GET /today`` reflects both -> confirm ``GET /entries`` date-range/category/tag filters
return the expected subset.

"now" for the timer start/stop pair is controlled (not asserted against wall-clock) by
monkeypatching ``app.repo.utc_now_iso`` as imported into ``app.routers.timer``, so the computed
duration is deterministic.
"""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from tests._time_helpers import freeze_module_now


def test_full_capture_lifecycle(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    # --- Setup: categories + tags -----------------------------------------------------------
    deep_work = client.post("/categories", json={"name": "Deep Work", "color": "#4C6EF5"}).json()
    meetings = client.post("/categories", json={"name": "Meetings"}).json()
    focus_tag = client.post("/tags", json={"name": "focus"}).json()
    urgent_tag = client.post("/tags", json={"name": "urgent"}).json()

    # --- Start timer, with a controlled start time -------------------------------------------
    start_instant = datetime(2026, 7, 13, 9, 0, 0, tzinfo=UTC)
    monkeypatch.setattr("app.routers.timer.utc_now_iso", lambda: start_instant.isoformat())
    start_response = client.post("/timer/start", json={"title": "Untitled work"})
    assert start_response.status_code == 201
    started = start_response.json()
    assert started["end_ts"] is None
    assert started["duration_minutes"] is None
    assert started["entry_mode"] == "timer"

    # --- GET /timer/current reflects the running entry ---------------------------------------
    current_response = client.get("/timer/current")
    assert current_response.status_code == 200
    current_body = current_response.json()
    assert current_body["running"] is True
    assert current_body["entry"]["id"] == started["id"]

    # --- Stop the timer 90 minutes later, assigning title/category/tags ----------------------
    stop_instant = datetime(2026, 7, 13, 10, 30, 0, tzinfo=UTC)
    monkeypatch.setattr("app.routers.timer.utc_now_iso", lambda: stop_instant.isoformat())
    stop_response = client.post(
        "/timer/stop",
        json={
            "title": "Write quarterly report",
            "category_id": deep_work["id"],
            "tag_ids": [focus_tag["id"], urgent_tag["id"]],
        },
    )
    assert stop_response.status_code == 200
    stopped = stop_response.json()
    assert stopped["id"] == started["id"]
    assert stopped["title"] == "Write quarterly report"
    assert stopped["end_ts"] is not None
    assert stopped["duration_minutes"] == 90.0
    assert stopped["category"]["id"] == deep_work["id"]
    assert {tag["id"] for tag in stopped["tags"]} == {focus_tag["id"], urgent_tag["id"]}

    # --- No timer running anymore --------------------------------------------------------------
    idle_response = client.get("/timer/current")
    assert idle_response.status_code == 200
    assert idle_response.json() == {"running": False, "entry": None}

    # --- Add a manual entry on the same day ---------------------------------------------------
    manual_response = client.post(
        "/entries",
        json={
            "title": "Client standup",
            "category_id": meetings["id"],
            "tag_ids": [urgent_tag["id"]],
            "start_ts": "2026-07-13T13:00:00+00:00",
            "end_ts": "2026-07-13T13:30:00+00:00",
        },
    )
    assert manual_response.status_code == 201
    manual_entry = manual_response.json()
    assert manual_entry["duration_minutes"] == 30.0
    assert manual_entry["entry_mode"] == "manual"

    # --- /today reflects both entries (with "now" still frozen at stop_instant) --------------
    freeze_module_now(monkeypatch, "app.routers.today.datetime", stop_instant)
    today_response = client.get("/today")
    assert today_response.status_code == 200
    today_body = today_response.json()
    today_entry_ids = {item["id"] for item in today_body["entries"]}
    assert today_entry_ids == {stopped["id"], manual_entry["id"]}
    assert today_body["running_timer"] is None
    assert {c["id"] for c in today_body["recent_categories"]} == {deep_work["id"], meetings["id"]}
    assert {t["id"] for t in today_body["recent_tags"]} == {focus_tag["id"], urgent_tag["id"]}

    # --- GET /entries: date-range filter -------------------------------------------------------
    date_range_response = client.get(
        "/entries", params={"start_date": "2026-07-13", "end_date": "2026-07-13"}
    )
    assert date_range_response.status_code == 200
    ids_in_range = {item["id"] for item in date_range_response.json()["items"]}
    assert ids_in_range == {stopped["id"], manual_entry["id"]}

    # --- GET /entries: category filter ----------------------------------------------------------
    category_filter_response = client.get("/entries", params={"category_id": deep_work["id"]})
    assert category_filter_response.status_code == 200
    ids_by_category = {item["id"] for item in category_filter_response.json()["items"]}
    assert ids_by_category == {stopped["id"]}

    # --- GET /entries: tag filter (both entries share the "urgent" tag) --------------------------
    tag_filter_response = client.get("/entries", params={"tag_id": urgent_tag["id"]})
    assert tag_filter_response.status_code == 200
    ids_by_tag = {item["id"] for item in tag_filter_response.json()["items"]}
    assert ids_by_tag == {stopped["id"], manual_entry["id"]}
