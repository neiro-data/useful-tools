"""Asserts the standard error envelope shape across a 404, a 409, a 422, and an unhandled 500."""

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


def test_unhandled_exception_yields_generic_500_envelope(client: TestClient) -> None:
    """A plain, otherwise-unhandled exception must still come back as the standard envelope,
    with a generic ``message`` — never the raw exception text or a stack trace."""

    @client.app.get("/__test_boom")  # type: ignore[union-attr]
    def _boom() -> None:
        raise RuntimeError("some sensitive internal detail that must not leak")

    response = TestClient(client.app, raise_server_exceptions=False).get("/__test_boom")

    assert response.status_code == 500
    body = response.json()
    _assert_envelope_shape(body)
    assert body["error"]["code"] == "internal_error"
    assert "sensitive internal detail" not in body["error"]["message"]
