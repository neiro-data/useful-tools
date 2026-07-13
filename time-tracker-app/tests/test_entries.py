"""Tests for the ``/entries`` endpoints."""

from fastapi.testclient import TestClient


def _make_category(client: TestClient, name: str = "Deep Work") -> int:
    response = client.post("/categories", json={"name": name})
    category_id: int = response.json()["id"]
    return category_id


def _make_tag(client: TestClient, name: str = "focus") -> int:
    response = client.post("/tags", json={"name": name})
    tag_id: int = response.json()["id"]
    return tag_id


def test_create_entry_computes_duration_server_side(client: TestClient) -> None:
    response = client.post(
        "/entries",
        json={
            "title": "Write report",
            "start_ts": "2026-07-13T09:00:00+00:00",
            "end_ts": "2026-07-13T10:30:00+00:00",
            "duration_minutes": 999999,  # must be ignored; not part of EntryCreateManual anyway
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["duration_minutes"] == 90.0
    assert body["entry_mode"] == "manual"


def test_create_entry_with_category_and_tags(client: TestClient) -> None:
    category_id = _make_category(client)
    tag_id = _make_tag(client)

    response = client.post(
        "/entries",
        json={
            "title": "Write report",
            "category_id": category_id,
            "tag_ids": [tag_id],
            "start_ts": "2026-07-13T09:00:00+00:00",
            "end_ts": "2026-07-13T10:00:00+00:00",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["category"]["id"] == category_id
    assert [tag["id"] for tag in body["tags"]] == [tag_id]


def test_create_entry_invalid_category_is_404(client: TestClient) -> None:
    response = client.post(
        "/entries",
        json={
            "title": "Write report",
            "category_id": 999,
            "start_ts": "2026-07-13T09:00:00+00:00",
            "end_ts": "2026-07-13T10:00:00+00:00",
        },
    )

    assert response.status_code == 404
    assert response.json()["error"]["details"] == {"category_id": 999}


def test_create_entry_invalid_tag_is_404(client: TestClient) -> None:
    response = client.post(
        "/entries",
        json={
            "title": "Write report",
            "tag_ids": [999],
            "start_ts": "2026-07-13T09:00:00+00:00",
            "end_ts": "2026-07-13T10:00:00+00:00",
        },
    )

    assert response.status_code == 404
    assert response.json()["error"]["details"] == {"tag_ids": [999]}


def test_create_entry_end_before_start_is_validation_error(client: TestClient) -> None:
    response = client.post(
        "/entries",
        json={
            "title": "Write report",
            "start_ts": "2026-07-13T10:00:00+00:00",
            "end_ts": "2026-07-13T09:00:00+00:00",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_get_entry_not_found(client: TestClient) -> None:
    response = client.get("/entries/999")

    assert response.status_code == 404


def test_update_entry_recomputes_duration(client: TestClient) -> None:
    entry = client.post(
        "/entries",
        json={
            "title": "Write report",
            "start_ts": "2026-07-13T09:00:00+00:00",
            "end_ts": "2026-07-13T10:00:00+00:00",
        },
    ).json()

    response = client.patch(f"/entries/{entry['id']}", json={"end_ts": "2026-07-13T11:00:00+00:00"})

    assert response.status_code == 200
    assert response.json()["duration_minutes"] == 120.0


def test_update_entry_clearing_end_ts_sets_duration_null(client: TestClient) -> None:
    entry = client.post(
        "/entries",
        json={
            "title": "Write report",
            "start_ts": "2026-07-13T09:00:00+00:00",
            "end_ts": "2026-07-13T10:00:00+00:00",
        },
    ).json()

    response = client.patch(f"/entries/{entry['id']}", json={"end_ts": None})

    assert response.status_code == 200
    body = response.json()
    assert body["end_ts"] is None
    assert body["duration_minutes"] is None


def test_update_entry_effective_end_before_start_is_validation_error(client: TestClient) -> None:
    entry = client.post(
        "/entries",
        json={
            "title": "Write report",
            "start_ts": "2026-07-13T09:00:00+00:00",
            "end_ts": "2026-07-13T10:00:00+00:00",
        },
    ).json()

    # Only start_ts is provided in this PATCH; effective end_ts (stored) is now before it.
    response = client.patch(
        f"/entries/{entry['id']}", json={"start_ts": "2026-07-13T11:00:00+00:00"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_update_entry_replaces_tags(client: TestClient) -> None:
    tag_a = _make_tag(client, "a")
    tag_b = _make_tag(client, "b")
    entry = client.post(
        "/entries",
        json={
            "title": "Write report",
            "tag_ids": [tag_a],
            "start_ts": "2026-07-13T09:00:00+00:00",
            "end_ts": "2026-07-13T10:00:00+00:00",
        },
    ).json()

    response = client.patch(f"/entries/{entry['id']}", json={"tag_ids": [tag_b]})

    assert response.status_code == 200
    assert [tag["id"] for tag in response.json()["tags"]] == [tag_b]


def test_update_entry_not_found(client: TestClient) -> None:
    response = client.patch("/entries/999", json={"title": "New title"})

    assert response.status_code == 404


def test_delete_entry(client: TestClient) -> None:
    entry = client.post(
        "/entries",
        json={
            "title": "Write report",
            "start_ts": "2026-07-13T09:00:00+00:00",
            "end_ts": "2026-07-13T10:00:00+00:00",
        },
    ).json()

    delete_response = client.delete(f"/entries/{entry['id']}")
    assert delete_response.status_code == 204

    get_response = client.get(f"/entries/{entry['id']}")
    assert get_response.status_code == 404


def test_delete_running_timer_entry_cancels_it(client: TestClient) -> None:
    """DELETE on the currently-running timer's entry is an allowed "cancel/discard the running
    timer" action: the entry is hard-deleted and no timer remains running afterwards."""
    started = client.post("/timer/start", json={"title": "Deep work"}).json()

    delete_response = client.delete(f"/entries/{started['id']}")
    assert delete_response.status_code == 204

    current_response = client.get("/timer/current")
    assert current_response.status_code == 200
    assert current_response.json() == {"running": False, "entry": None}

    get_response = client.get(f"/entries/{started['id']}")
    assert get_response.status_code == 404


def test_delete_entry_not_found(client: TestClient) -> None:
    response = client.delete("/entries/999")

    assert response.status_code == 404


def test_list_entries_filters_by_date_range(client: TestClient) -> None:
    in_range = client.post(
        "/entries",
        json={
            "title": "In range",
            "start_ts": "2026-07-13T09:00:00+00:00",
            "end_ts": "2026-07-13T10:00:00+00:00",
        },
    ).json()
    out_of_range = client.post(
        "/entries",
        json={
            "title": "Out of range",
            "start_ts": "2026-08-01T09:00:00+00:00",
            "end_ts": "2026-08-01T10:00:00+00:00",
        },
    ).json()

    response = client.get("/entries", params={"start_date": "2026-07-01", "end_date": "2026-07-31"})

    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert in_range["id"] in ids
    assert out_of_range["id"] not in ids


def test_list_entries_filters_by_category(client: TestClient) -> None:
    category_id = _make_category(client)
    matching = client.post(
        "/entries",
        json={
            "title": "Matching",
            "category_id": category_id,
            "start_ts": "2026-07-13T09:00:00+00:00",
            "end_ts": "2026-07-13T10:00:00+00:00",
        },
    ).json()
    other = client.post(
        "/entries",
        json={
            "title": "Other",
            "start_ts": "2026-07-13T09:00:00+00:00",
            "end_ts": "2026-07-13T10:00:00+00:00",
        },
    ).json()

    response = client.get("/entries", params={"category_id": category_id})

    ids = {item["id"] for item in response.json()["items"]}
    assert matching["id"] in ids
    assert other["id"] not in ids


def test_list_entries_filters_by_tag(client: TestClient) -> None:
    tag_id = _make_tag(client)
    matching = client.post(
        "/entries",
        json={
            "title": "Matching",
            "tag_ids": [tag_id],
            "start_ts": "2026-07-13T09:00:00+00:00",
            "end_ts": "2026-07-13T10:00:00+00:00",
        },
    ).json()
    other = client.post(
        "/entries",
        json={
            "title": "Other",
            "start_ts": "2026-07-13T09:00:00+00:00",
            "end_ts": "2026-07-13T10:00:00+00:00",
        },
    ).json()

    response = client.get("/entries", params={"tag_id": tag_id})

    ids = {item["id"] for item in response.json()["items"]}
    assert matching["id"] in ids
    assert other["id"] not in ids


def test_list_entries_filters_by_deactivated_category_still_returns_historical_entries(
    client: TestClient,
) -> None:
    category_id = _make_category(client, "Retired Category")
    historical = client.post(
        "/entries",
        json={
            "title": "Historical work",
            "category_id": category_id,
            "start_ts": "2026-07-13T09:00:00+00:00",
            "end_ts": "2026-07-13T10:00:00+00:00",
        },
    ).json()

    client.post(f"/categories/{category_id}/deactivate")

    response = client.get("/entries", params={"category_id": category_id})

    assert response.status_code == 200
    body = response.json()
    ids = {item["id"] for item in body["items"]}
    assert historical["id"] in ids
    assert body["items"][0]["category"]["is_active"] is False


def test_list_entries_end_date_before_start_date_is_validation_error(client: TestClient) -> None:
    response = client.get("/entries", params={"start_date": "2026-07-31", "end_date": "2026-07-01"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
