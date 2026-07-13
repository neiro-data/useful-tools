"""Tests for the ``/categories`` endpoints."""

from fastapi.testclient import TestClient


def test_create_and_get_category(client: TestClient) -> None:
    create_response = client.post("/categories", json={"name": "Deep Work", "color": "#4C6EF5"})
    assert create_response.status_code == 201
    body = create_response.json()
    assert body["name"] == "Deep Work"
    assert body["color"] == "#4C6EF5"
    assert body["is_active"] is True
    assert body["sort_order"] == 0

    get_response = client.get(f"/categories/{body['id']}")
    assert get_response.status_code == 200
    assert get_response.json() == body


def test_create_category_duplicate_name_is_conflict(client: TestClient) -> None:
    client.post("/categories", json={"name": "Deep Work"})

    response = client.post("/categories", json={"name": "Deep Work"})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_create_category_blank_name_is_validation_error(client: TestClient) -> None:
    response = client.post("/categories", json={"name": ""})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_list_categories_excludes_inactive_by_default(client: TestClient) -> None:
    active = client.post("/categories", json={"name": "Active"}).json()
    inactive = client.post("/categories", json={"name": "Inactive"}).json()
    client.post(f"/categories/{inactive['id']}/deactivate")

    response = client.get("/categories")

    assert response.status_code == 200
    body = response.json()
    ids = {item["id"] for item in body["items"]}
    assert active["id"] in ids
    assert inactive["id"] not in ids


def test_list_categories_include_inactive(client: TestClient) -> None:
    inactive = client.post("/categories", json={"name": "Inactive"}).json()
    client.post(f"/categories/{inactive['id']}/deactivate")

    response = client.get("/categories", params={"include_inactive": True})

    ids = {item["id"] for item in response.json()["items"]}
    assert inactive["id"] in ids


def test_get_category_not_found(client: TestClient) -> None:
    response = client.get("/categories/999")

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "resource_not_found"
    assert error["details"] == {"category_id": 999}


def test_update_category_partial(client: TestClient) -> None:
    category = client.post("/categories", json={"name": "Deep Work", "sort_order": 1}).json()

    response = client.patch(f"/categories/{category['id']}", json={"color": "#000000"})

    assert response.status_code == 200
    body = response.json()
    assert body["color"] == "#000000"
    assert body["name"] == "Deep Work"
    assert body["sort_order"] == 1


def test_update_category_name_collision_is_conflict(client: TestClient) -> None:
    client.post("/categories", json={"name": "First"})
    second = client.post("/categories", json={"name": "Second"}).json()

    response = client.patch(f"/categories/{second['id']}", json={"name": "First"})

    assert response.status_code == 409


def test_deactivate_category_is_idempotent(client: TestClient) -> None:
    category = client.post("/categories", json={"name": "Deep Work"}).json()

    first = client.post(f"/categories/{category['id']}/deactivate")
    second = client.post(f"/categories/{category['id']}/deactivate")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["is_active"] is False
    assert second.json()["is_active"] is False


def test_deactivated_category_still_resolvable_on_historical_entry(client: TestClient) -> None:
    category = client.post("/categories", json={"name": "Deep Work"}).json()
    entry = client.post(
        "/entries",
        json={
            "title": "Some work",
            "category_id": category["id"],
            "start_ts": "2026-07-13T09:00:00+00:00",
            "end_ts": "2026-07-13T10:00:00+00:00",
        },
    ).json()

    client.post(f"/categories/{category['id']}/deactivate")

    response = client.get(f"/entries/{entry['id']}")

    assert response.status_code == 200
    assert response.json()["category"]["id"] == category["id"]
    assert response.json()["category"]["is_active"] is False
