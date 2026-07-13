"""Tests for the ``/tags`` endpoints."""

from fastapi.testclient import TestClient


def test_create_and_get_tag(client: TestClient) -> None:
    create_response = client.post("/tags", json={"name": "focus"})
    assert create_response.status_code == 201
    body = create_response.json()
    assert body["name"] == "focus"
    assert body["is_active"] is True

    get_response = client.get(f"/tags/{body['id']}")
    assert get_response.status_code == 200
    assert get_response.json() == body


def test_create_tag_duplicate_name_is_conflict(client: TestClient) -> None:
    client.post("/tags", json={"name": "focus"})

    response = client.post("/tags", json={"name": "focus"})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_list_tags_excludes_inactive_by_default(client: TestClient) -> None:
    active = client.post("/tags", json={"name": "active-tag"}).json()
    inactive = client.post("/tags", json={"name": "inactive-tag"}).json()
    client.post(f"/tags/{inactive['id']}/deactivate")

    response = client.get("/tags")

    ids = {item["id"] for item in response.json()["items"]}
    assert active["id"] in ids
    assert inactive["id"] not in ids


def test_get_tag_not_found(client: TestClient) -> None:
    response = client.get("/tags/999")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "resource_not_found"


def test_update_tag_partial(client: TestClient) -> None:
    tag = client.post("/tags", json={"name": "focus"}).json()

    response = client.patch(f"/tags/{tag['id']}", json={"name": "deep-focus"})

    assert response.status_code == 200
    assert response.json()["name"] == "deep-focus"


def test_deactivate_tag_is_idempotent(client: TestClient) -> None:
    tag = client.post("/tags", json={"name": "focus"}).json()

    first = client.post(f"/tags/{tag['id']}/deactivate")
    second = client.post(f"/tags/{tag['id']}/deactivate")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["is_active"] is False
    assert second.json()["is_active"] is False
