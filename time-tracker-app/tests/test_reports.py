"""Tests for the ``GET /reports/summary`` aggregation endpoint."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.db import get_connection
from tests._time_helpers import freeze_module_now


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


def _set_timezone(timezone: str) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE settings SET timezone = ?", (timezone,))
        conn.commit()


def _build_fixture(client: TestClient) -> dict[str, int]:
    """Builds a fixed scenario anchored around 2026-07-15 (a Wednesday):

    - week:    2026-07-13 (Mon) .. 2026-07-19 (Sun)
    - month:   2026-07-01 .. 2026-07-31
    - quarter: 2026-07-01 .. 2026-09-30

    Entries (all times UTC, default ``settings.timezone``):
    - A: cat1, tags [1, 2], 60 min, 2026-07-13T10:00 (week start day)
    - B: cat1, tag [1], 90 min, 2026-07-15T10:00 (mid-week)
    - C: no category/tags, 45 min, 2026-07-19T20:00 (week end day)
    - D: cat2, no tags, 30 min, 2026-07-25 (in month, not in week)
    - E: no category/tags, 15 min, 2026-09-01 (in quarter, not in month)
    - F: no category/tags, 20 min, 2026-10-01 (outside the quarter entirely)
    """
    cat1 = _make_category(client, "Deep Work")
    cat2 = _make_category(client, "Meetings")
    tag1 = _make_tag(client, "focus")
    tag2 = _make_tag(client, "urgent")

    entry_a = _make_entry(
        client,
        "A",
        "2026-07-13T10:00:00+00:00",
        "2026-07-13T11:00:00+00:00",
        category_id=cat1,
        tag_ids=[tag1, tag2],
    )
    entry_b = _make_entry(
        client,
        "B",
        "2026-07-15T10:00:00+00:00",
        "2026-07-15T11:30:00+00:00",
        category_id=cat1,
        tag_ids=[tag1],
    )
    entry_c = _make_entry(client, "C", "2026-07-19T20:00:00+00:00", "2026-07-19T20:45:00+00:00")
    entry_d = _make_entry(
        client,
        "D",
        "2026-07-25T10:00:00+00:00",
        "2026-07-25T10:30:00+00:00",
        category_id=cat2,
    )
    entry_e = _make_entry(client, "E", "2026-09-01T10:00:00+00:00", "2026-09-01T10:15:00+00:00")
    entry_f = _make_entry(client, "F", "2026-10-01T10:00:00+00:00", "2026-10-01T10:20:00+00:00")

    return {
        "cat1": cat1,
        "cat2": cat2,
        "tag1": tag1,
        "tag2": tag2,
        "entry_a": entry_a,
        "entry_b": entry_b,
        "entry_c": entry_c,
        "entry_d": entry_d,
        "entry_e": entry_e,
        "entry_f": entry_f,
    }


def test_reports_summary_week_no_entries_is_empty(client: TestClient) -> None:
    response = client.get("/reports/summary", params={"period": "week", "date": "2026-07-15"})

    assert response.status_code == 200
    body = response.json()
    assert body["period"] == "week"
    assert body["start_date"] == "2026-07-13"
    assert body["end_date"] == "2026-07-19"
    assert body["timezone"] == "UTC"
    assert body["total_minutes"] == 0
    assert body["entry_count"] == 0
    assert body["by_category"] == []
    assert body["by_tag"] == []
    assert body["by_day"] == []


def test_reports_summary_week_aggregates_and_sorts(client: TestClient) -> None:
    fixture = _build_fixture(client)

    response = client.get("/reports/summary", params={"period": "week", "date": "2026-07-15"})

    assert response.status_code == 200
    body = response.json()
    assert body["start_date"] == "2026-07-13"
    assert body["end_date"] == "2026-07-19"
    assert body["total_minutes"] == 195
    assert body["entry_count"] == 3

    by_category = body["by_category"]
    assert [c["category"]["id"] if c["category"] else None for c in by_category] == [
        fixture["cat1"],
        None,
    ]
    assert [(c["total_minutes"], c["entry_count"]) for c in by_category] == [(150, 2), (45, 1)]

    by_tag = body["by_tag"]
    assert [t["tag"]["id"] for t in by_tag] == [fixture["tag1"], fixture["tag2"]]
    assert [(t["total_minutes"], t["entry_count"]) for t in by_tag] == [(150, 2), (60, 1)]

    by_day = body["by_day"]
    assert [(d["date"], d["total_minutes"], d["entry_count"]) for d in by_day] == [
        ("2026-07-13", 60, 1),
        ("2026-07-15", 90, 1),
        ("2026-07-19", 45, 1),
    ]

    # Entries outside the week (D, E, F) must not be counted.
    assert fixture["entry_d"] not in {
        item for c in by_category if c["category"] for item in [c["category"]["id"]]
    }


def test_reports_summary_month_aggregates_and_sorts(client: TestClient) -> None:
    fixture = _build_fixture(client)

    response = client.get("/reports/summary", params={"period": "month", "date": "2026-07-15"})

    assert response.status_code == 200
    body = response.json()
    assert body["start_date"] == "2026-07-01"
    assert body["end_date"] == "2026-07-31"
    assert body["total_minutes"] == 225
    assert body["entry_count"] == 4

    by_category = body["by_category"]
    # None (45) sorts ahead of cat2 (30) even though cat1 (150) is still first.
    assert [c["category"]["id"] if c["category"] else None for c in by_category] == [
        fixture["cat1"],
        None,
        fixture["cat2"],
    ]
    assert [(c["total_minutes"], c["entry_count"]) for c in by_category] == [
        (150, 2),
        (45, 1),
        (30, 1),
    ]

    by_tag = body["by_tag"]
    assert [(t["tag"]["id"], t["total_minutes"], t["entry_count"]) for t in by_tag] == [
        (fixture["tag1"], 150, 2),
        (fixture["tag2"], 60, 1),
    ]

    by_day = body["by_day"]
    assert [d["date"] for d in by_day] == ["2026-07-13", "2026-07-15", "2026-07-19", "2026-07-25"]


def test_reports_summary_quarter_aggregates_and_sorts(client: TestClient) -> None:
    fixture = _build_fixture(client)

    response = client.get("/reports/summary", params={"period": "quarter", "date": "2026-07-15"})

    assert response.status_code == 200
    body = response.json()
    assert body["start_date"] == "2026-07-01"
    assert body["end_date"] == "2026-09-30"
    assert body["total_minutes"] == 240
    assert body["entry_count"] == 5

    by_category = body["by_category"]
    assert [c["category"]["id"] if c["category"] else None for c in by_category] == [
        fixture["cat1"],
        None,
        fixture["cat2"],
    ]
    assert [(c["total_minutes"], c["entry_count"]) for c in by_category] == [
        (150, 2),
        (60, 2),
        (30, 1),
    ]

    by_day = body["by_day"]
    assert [d["date"] for d in by_day] == [
        "2026-07-13",
        "2026-07-15",
        "2026-07-19",
        "2026-07-25",
        "2026-09-01",
    ]

    # F (2026-10-01) is outside even the quarter.
    fetched_dates = {d["date"] for d in by_day}
    assert "2026-10-01" not in fetched_dates


def test_reports_summary_by_tag_double_counts_multi_tag_entries(client: TestClient) -> None:
    """An entry linked to two tags contributes its full duration to *each* tag, so
    ``sum(by_tag totals)`` may exceed ``total_minutes`` (documented, intentional behavior)."""
    fixture = _build_fixture(client)

    response = client.get("/reports/summary", params={"period": "week", "date": "2026-07-15"})

    body = response.json()
    tag_total = sum(t["total_minutes"] for t in body["by_tag"])
    assert tag_total == 210  # 150 (tag1) + 60 (tag2), vs total_minutes == 195
    assert tag_total > body["total_minutes"]
    assert fixture["tag1"] != fixture["tag2"]


def test_reports_summary_excludes_running_timer(client: TestClient) -> None:
    today = datetime.now(UTC).date().isoformat()
    _make_entry(client, "Completed", f"{today}T08:00:00+00:00", f"{today}T09:00:00+00:00")
    client.post("/timer/start", json={"title": "Still running"})

    response = client.get("/reports/summary", params={"period": "week"})

    assert response.status_code == 200
    body = response.json()
    assert body["total_minutes"] == 60
    assert body["entry_count"] == 1


def test_reports_summary_date_defaults_to_today(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    frozen_now = datetime(2026, 7, 15, 12, 0, 0, tzinfo=UTC)
    freeze_module_now(monkeypatch, "app.routers.reports.datetime", frozen_now)

    response = client.get("/reports/summary", params={"period": "week"})

    assert response.status_code == 200
    body = response.json()
    assert body["start_date"] == "2026-07-13"
    assert body["end_date"] == "2026-07-19"


def test_reports_summary_boundary_entries_included_at_period_edges(client: TestClient) -> None:
    """An entry exactly at the first instant of the period start and one exactly at the last
    instant of the period end must both be included (inclusive bounds)."""
    start_edge = _make_entry(
        client, "Start edge", "2026-07-13T00:00:00+00:00", "2026-07-13T00:15:00+00:00"
    )
    end_edge = _make_entry(
        client, "End edge", "2026-07-19T23:59:00+00:00", "2026-07-19T23:59:59+00:00"
    )
    just_outside = _make_entry(
        client, "Just outside", "2026-07-20T00:00:00+00:00", "2026-07-20T00:15:00+00:00"
    )

    response = client.get("/reports/summary", params={"period": "week", "date": "2026-07-15"})

    assert response.status_code == 200
    body = response.json()
    assert body["entry_count"] == 2
    dates = {d["date"] for d in body["by_day"]}
    assert dates == {"2026-07-13", "2026-07-19"}
    assert start_edge != end_edge != just_outside


def test_reports_summary_invalid_period_is_validation_error(client: TestClient) -> None:
    response = client.get("/reports/summary", params={"period": "decade"})

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert isinstance(body["error"]["details"]["fields"], list)


def test_reports_summary_day_boundary_resolves_against_configured_timezone(
    client: TestClient,
) -> None:
    """Regression test for the tz-boundary bug: an entry whose UTC instant falls on the *last*
    UTC calendar day of the week, but on the *first* day of the *following* local week once
    ``settings.timezone`` is non-UTC, must flip membership accordingly — proving both
    ``/reports/summary`` and ``/entries`` resolve local-day boundaries, not naive UTC midnight.
    """
    # 2026-07-19T20:00:00Z is Sunday (last day of the 07-13..07-19 week) in UTC, but
    # 2026-07-20T05:00:00 Asia/Tokyo (+9) -- Monday, i.e. the *next* local week.
    entry = _make_entry(
        client, "Boundary entry", "2026-07-19T20:00:00+00:00", "2026-07-19T20:30:00+00:00"
    )

    # Default settings timezone is UTC: the entry's local day is 2026-07-19, inside the week.
    utc_report = client.get(
        "/reports/summary", params={"period": "week", "date": "2026-07-15"}
    ).json()
    assert utc_report["entry_count"] == 1
    utc_entries = client.get(
        "/entries", params={"start_date": "2026-07-13", "end_date": "2026-07-19"}
    ).json()
    assert entry in {item["id"] for item in utc_entries["items"]}

    # Switch to Asia/Tokyo: the entry's local day is 2026-07-20, outside the week.
    _set_timezone("Asia/Tokyo")

    tokyo_report = client.get(
        "/reports/summary", params={"period": "week", "date": "2026-07-15"}
    ).json()
    assert tokyo_report["entry_count"] == 0
    tokyo_entries = client.get(
        "/entries", params={"start_date": "2026-07-13", "end_date": "2026-07-19"}
    ).json()
    assert entry not in {item["id"] for item in tokyo_entries["items"]}
