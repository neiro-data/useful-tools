"""Tests for the ``/settings`` singleton endpoints. See ``app/routers/settings.py``."""

from fastapi.testclient import TestClient

from app.config import get_settings
from app.db import get_connection


def _settings_row_count() -> int:
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM settings").fetchone()
        return int(row["count"])


def test_get_settings_returns_seeded_defaults(client: TestClient) -> None:
    response = client.get("/settings")

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "id",
        "default_entry_mode",
        "week_starts_on",
        "default_export_format",
        "database_label",
        "timezone",
    }
    assert body["default_entry_mode"] == "timer"
    assert body["week_starts_on"] == "monday"
    assert body["default_export_format"] == "md"
    assert body["database_label"] == get_settings().app_name
    assert body["timezone"] == "UTC"


def test_patch_single_field_changes_only_that_field(client: TestClient) -> None:
    before = client.get("/settings").json()

    response = client.patch("/settings", json={"timezone": "Asia/Tokyo"})

    assert response.status_code == 200
    body = response.json()
    assert body["timezone"] == "Asia/Tokyo"
    for field in (
        "id",
        "default_entry_mode",
        "week_starts_on",
        "default_export_format",
        "database_label",
    ):
        assert body[field] == before[field]

    follow_up = client.get("/settings").json()
    assert follow_up["timezone"] == "Asia/Tokyo"


def test_patch_multiple_fields_at_once(client: TestClient) -> None:
    response = client.patch(
        "/settings",
        json={
            "default_entry_mode": "manual",
            "week_starts_on": "sunday",
            "default_export_format": "csv",
            "database_label": "My DB",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["default_entry_mode"] == "manual"
    assert body["week_starts_on"] == "sunday"
    assert body["default_export_format"] == "csv"
    assert body["database_label"] == "My DB"
    assert body["timezone"] == "UTC"


def test_patch_empty_body_is_a_no_op(client: TestClient) -> None:
    before = client.get("/settings").json()

    response = client.patch("/settings", json={})

    assert response.status_code == 200
    assert response.json() == before

    after = client.get("/settings").json()
    assert after == before


def test_patch_invalid_timezone_returns_422(client: TestClient) -> None:
    response = client.patch("/settings", json={"timezone": "Mars/Phobos"})

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert isinstance(body["error"]["details"]["fields"], list)
    assert len(body["error"]["details"]["fields"]) > 0
    for field in body["error"]["details"]["fields"]:
        assert "loc" in field
        assert "msg" in field


def test_patch_blank_database_label_returns_422(client: TestClient) -> None:
    response = client.patch("/settings", json={"database_label": "   "})

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"


def test_patch_invalid_default_entry_mode_returns_422(client: TestClient) -> None:
    response = client.patch("/settings", json={"default_entry_mode": "not-a-mode"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_patch_invalid_week_starts_on_returns_422(client: TestClient) -> None:
    response = client.patch("/settings", json={"week_starts_on": "not-a-day"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_patch_invalid_default_export_format_returns_422(client: TestClient) -> None:
    response = client.patch("/settings", json={"default_export_format": "not-a-format"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_settings_table_stays_a_singleton_after_multiple_patches(client: TestClient) -> None:
    client.patch("/settings", json={"timezone": "Europe/Lisbon"})
    client.patch("/settings", json={"default_entry_mode": "manual"})
    client.patch("/settings", json={})
    client.patch(
        "/settings",
        json={"week_starts_on": "sunday", "default_export_format": "pdf"},
    )

    assert _settings_row_count() == 1


def test_patch_timezone_round_trips_through_get(client: TestClient) -> None:
    patch_response = client.patch("/settings", json={"timezone": "America/Sao_Paulo"})
    assert patch_response.status_code == 200
    assert patch_response.json()["timezone"] == "America/Sao_Paulo"

    get_response = client.get("/settings")
    assert get_response.status_code == 200
    assert get_response.json()["timezone"] == "America/Sao_Paulo"
