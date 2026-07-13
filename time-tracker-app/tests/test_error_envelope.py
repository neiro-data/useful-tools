"""Asserts the standard error envelope shape across a 404, a 409, and a 422."""

from fastapi.testclient import TestClient


def _assert_envelope_shape(body: dict) -> None:
    assert set(body.keys()) == {"error"}
    error = body["error"]
    assert "code" in error
    assert "message" in error
    assert "details" in error
    assert isinstance(error["code"], str)
    assert isinstance(error["message"], str)


def test_404_error_envelope_shape(client: TestClient) -> None:
    response = client.get("/categories/999")

    assert response.status_code == 404
    body = response.json()
    _assert_envelope_shape(body)
    assert body["error"]["code"] == "resource_not_found"


def test_409_error_envelope_shape(client: TestClient) -> None:
    client.post("/categories", json={"name": "Duplicate"})

    response = client.post("/categories", json={"name": "Duplicate"})

    assert response.status_code == 409
    body = response.json()
    _assert_envelope_shape(body)
    assert body["error"]["code"] == "conflict"


def test_422_error_envelope_shape(client: TestClient) -> None:
    response = client.post("/categories", json={"name": ""})

    assert response.status_code == 422
    body = response.json()
    _assert_envelope_shape(body)
    assert body["error"]["code"] == "validation_error"
    assert isinstance(body["error"]["details"]["fields"], list)
    assert len(body["error"]["details"]["fields"]) > 0
    for field in body["error"]["details"]["fields"]:
        assert "loc" in field
        assert "msg" in field
