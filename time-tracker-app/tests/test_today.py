"""Tests for the ``/today`` aggregation endpoint."""

from datetime import UTC, datetime

from fastapi.testclient import TestClient


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
