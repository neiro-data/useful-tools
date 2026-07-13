"""Tests for the ``/timer`` endpoints and the single-active-timer rule."""

from fastapi.testclient import TestClient


def test_timer_lifecycle_start_current_stop(client: TestClient) -> None:
    start_response = client.post("/timer/start", json={"title": "Deep work"})
    assert start_response.status_code == 201
    started = start_response.json()
    assert started["end_ts"] is None
    assert started["duration_minutes"] is None
    assert started["entry_mode"] == "timer"

    current_response = client.get("/timer/current")
    assert current_response.status_code == 200
    current_body = current_response.json()
    assert current_body["running"] is True
    assert current_body["entry"]["id"] == started["id"]

    stop_response = client.post("/timer/stop", json={"title": "Deep work (final)"})
    assert stop_response.status_code == 200
    stopped = stop_response.json()
    assert stopped["id"] == started["id"]
    assert stopped["title"] == "Deep work (final)"
    assert stopped["end_ts"] is not None
    assert stopped["duration_minutes"] is not None
    assert stopped["duration_minutes"] >= 0

    idle_response = client.get("/timer/current")
    assert idle_response.status_code == 200
    assert idle_response.json() == {"running": False, "entry": None}


def test_timer_start_default_title(client: TestClient) -> None:
    response = client.post("/timer/start", json={})

    assert response.status_code == 201
    assert response.json()["title"] == "Untitled"


def test_starting_second_timer_is_conflict(client: TestClient) -> None:
    first = client.post("/timer/start", json={"title": "First"}).json()

    response = client.post("/timer/start", json={"title": "Second"})

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "timer_already_running"
    assert error["details"] == {"running_entry_id": first["id"]}

    # existing timer left untouched, no new entry created
    current = client.get("/timer/current").json()
    assert current["entry"]["id"] == first["id"]
    assert current["entry"]["title"] == "First"


def test_stopping_with_no_running_timer_is_conflict(client: TestClient) -> None:
    response = client.post("/timer/stop", json={})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "no_running_timer"


def test_timer_current_when_idle(client: TestClient) -> None:
    response = client.get("/timer/current")

    assert response.status_code == 200
    assert response.json() == {"running": False, "entry": None}


def test_timer_start_invalid_category_is_404(client: TestClient) -> None:
    response = client.post("/timer/start", json={"category_id": 999})

    assert response.status_code == 404


def test_timer_stop_can_assign_category_and_tags(client: TestClient) -> None:
    category_response = client.post("/categories", json={"name": "Deep Work"})
    category_id = category_response.json()["id"]
    tag_response = client.post("/tags", json={"name": "focus"})
    tag_id = tag_response.json()["id"]

    client.post("/timer/start", json={})

    response = client.post(
        "/timer/stop", json={"category_id": category_id, "tag_ids": [tag_id]}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["category"]["id"] == category_id
    assert [tag["id"] for tag in body["tags"]] == [tag_id]
