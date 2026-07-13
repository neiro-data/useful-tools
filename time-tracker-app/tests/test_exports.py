"""Tests for the ``/exports`` endpoints. See ``app/routers/exports.py``."""

import csv
import io

from fastapi.testclient import TestClient

SQLITE_MAGIC_HEADER = b"SQLite format 3\x00"


def _make_category(client: TestClient, name: str = "Deep Work") -> int:
    response = client.post("/categories", json={"name": name})
    category_id: int = response.json()["id"]
    return category_id


def _make_tag(client: TestClient, name: str = "focus") -> int:
    response = client.post("/tags", json={"name": name})
    tag_id: int = response.json()["id"]
    return tag_id


def _make_entry(
    client: TestClient,
    title: str,
    start_ts: str,
    end_ts: str,
    category_id: int | None = None,
    tag_ids: list[int] | None = None,
) -> int:
    response = client.post(
        "/entries",
        json={
            "title": title,
            "category_id": category_id,
            "tag_ids": tag_ids or [],
            "start_ts": start_ts,
            "end_ts": end_ts,
        },
    )
    entry_id: int = response.json()["id"]
    return entry_id


def _parse_csv(body: bytes) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(body.decode("utf-8")))
    return list(reader)


# --- backup -----------------------------------------------------------------


def test_export_backup_returns_octet_stream_attachment(client: TestClient) -> None:
    _make_category(client, "Deep Work")

    response = client.get("/exports/backup")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/octet-stream"
    content_disposition = response.headers["content-disposition"]
    assert content_disposition.startswith("attachment;")
    assert ".sqlite" in content_disposition


def test_export_backup_body_is_a_valid_sqlite_file(client: TestClient) -> None:
    response = client.get("/exports/backup")

    assert response.status_code == 200
    assert len(response.content) > 0
    assert response.content.startswith(SQLITE_MAGIC_HEADER)


# --- entries.csv --------------------------------------------------------------


def test_export_entries_csv_returns_csv_attachment(client: TestClient) -> None:
    response = client.get("/exports/entries.csv")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    content_disposition = response.headers["content-disposition"]
    assert content_disposition.startswith("attachment;")
    assert content_disposition.strip().endswith('.csv"')


def test_export_entries_csv_header_row(client: TestClient) -> None:
    response = client.get("/exports/entries.csv")

    assert response.status_code == 200
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8"))))
    assert rows[0] == [
        "id",
        "title",
        "category",
        "start_ts",
        "end_ts",
        "duration_minutes",
        "entry_mode",
        "tags",
        "notes",
    ]


def test_export_entries_csv_includes_completed_entry_with_category_and_tags(
    client: TestClient,
) -> None:
    category_id = _make_category(client, "Deep Work")
    tag1 = _make_tag(client, "focus")
    tag2 = _make_tag(client, "urgent")
    entry_id = _make_entry(
        client,
        "Completed entry",
        "2026-07-13T10:00:00+00:00",
        "2026-07-13T11:00:00+00:00",
        category_id=category_id,
        tag_ids=[tag1, tag2],
    )

    response = client.get("/exports/entries.csv")

    assert response.status_code == 200
    rows = _parse_csv(response.content)
    matching = [row for row in rows if row["id"] == str(entry_id)]
    assert len(matching) == 1
    row = matching[0]
    assert row["title"] == "Completed entry"
    assert row["category"] == "Deep Work"
    assert row["tags"] == "focus; urgent"
    assert float(row["duration_minutes"]) == 60


def test_export_entries_csv_excludes_running_timer(client: TestClient) -> None:
    completed_id = _make_entry(
        client, "Completed", "2026-07-13T10:00:00+00:00", "2026-07-13T11:00:00+00:00"
    )
    client.post("/timer/start", json={"title": "Still running"})

    response = client.get("/exports/entries.csv")

    assert response.status_code == 200
    rows = _parse_csv(response.content)
    titles = {row["title"] for row in rows}
    ids = {row["id"] for row in rows}
    assert "Still running" not in titles
    assert str(completed_id) in ids
    assert len(rows) == 1


def test_export_entries_csv_filters_by_date_range(client: TestClient) -> None:
    in_range = _make_entry(
        client, "In range", "2026-07-15T10:00:00+00:00", "2026-07-15T11:00:00+00:00"
    )
    out_of_range = _make_entry(
        client, "Out of range", "2026-08-01T10:00:00+00:00", "2026-08-01T11:00:00+00:00"
    )

    response = client.get(
        "/exports/entries.csv",
        params={"start_date": "2026-07-13", "end_date": "2026-07-19"},
    )

    assert response.status_code == 200
    rows = _parse_csv(response.content)
    ids = {row["id"] for row in rows}
    assert str(in_range) in ids
    assert str(out_of_range) not in ids


def test_export_entries_csv_end_date_before_start_date_is_validation_error(
    client: TestClient,
) -> None:
    response = client.get(
        "/exports/entries.csv",
        params={"start_date": "2026-07-19", "end_date": "2026-07-13"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert isinstance(body["error"]["details"]["fields"], list)


# --- report.html --------------------------------------------------------------


def test_export_report_html_returns_inline_html(client: TestClient) -> None:
    response = client.get("/exports/report.html", params={"period": "week", "date": "2026-07-15"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    content_disposition = response.headers.get("content-disposition", "")
    assert "attachment" not in content_disposition


def test_export_report_html_contains_period_range_and_category(client: TestClient) -> None:
    category_id = _make_category(client, "Deep Work")
    _make_entry(
        client,
        "Entry",
        "2026-07-15T10:00:00+00:00",
        "2026-07-15T11:00:00+00:00",
        category_id=category_id,
    )

    response = client.get("/exports/report.html", params={"period": "week", "date": "2026-07-15"})

    assert response.status_code == 200
    body = response.text
    assert "Week" in body
    assert "2026-07-13" in body
    assert "2026-07-19" in body
    assert "Deep Work" in body


def test_export_report_html_is_self_contained(client: TestClient) -> None:
    response = client.get("/exports/report.html", params={"period": "month", "date": "2026-07-15"})

    assert response.status_code == 200
    body = response.text
    assert "<link" not in body
    assert "<script" not in body


def test_export_report_html_requires_period(client: TestClient) -> None:
    response = client.get("/exports/report.html")

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
