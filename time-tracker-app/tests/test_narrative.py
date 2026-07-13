"""Tests for the ``GET /reports/narrative`` rule-based summary endpoint."""

from fastapi.testclient import TestClient


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


def _build_week_fixture(client: TestClient) -> dict[str, int]:
    """Builds a scenario within the 2026-07-13..2026-07-19 (Mon-Sun) week:

    - A: cat1 (Deep Work), tag1, 120 min, 2026-07-13 (Monday) -- busiest day
    - B: cat1 (Deep Work), tag1, 60 min, 2026-07-14 (Tuesday)
    - C: cat2 (Meetings), no tags, 60 min, 2026-07-15 (Wednesday)
    """
    cat1 = _make_category(client, "Deep Work")
    cat2 = _make_category(client, "Meetings")
    tag1 = _make_tag(client, "focus")

    entry_a = _make_entry(
        client,
        "A",
        "2026-07-13T09:00:00+00:00",
        "2026-07-13T11:00:00+00:00",
        category_id=cat1,
        tag_ids=[tag1],
    )
    entry_b = _make_entry(
        client,
        "B",
        "2026-07-14T09:00:00+00:00",
        "2026-07-14T10:00:00+00:00",
        category_id=cat1,
        tag_ids=[tag1],
    )
    entry_c = _make_entry(
        client,
        "C",
        "2026-07-15T09:00:00+00:00",
        "2026-07-15T10:00:00+00:00",
        category_id=cat2,
    )

    return {
        "cat1": cat1,
        "cat2": cat2,
        "tag1": tag1,
        "entry_a": entry_a,
        "entry_b": entry_b,
        "entry_c": entry_c,
    }


def test_narrative_empty_period_has_no_time_tracked_highlight(client: TestClient) -> None:
    response = client.get("/reports/narrative", params={"period": "week", "date": "2026-07-15"})

    assert response.status_code == 200
    body = response.json()
    assert body["period"] == "week"
    assert body["start_date"] == "2026-07-13"
    assert body["end_date"] == "2026-07-19"
    assert body["timezone"] == "UTC"
    assert len(body["highlights"]) == 1
    assert "no time tracked" in body["highlights"][0].lower()
    assert "no time tracked" in body["narrative"].lower()
    assert "2026-07-13" in body["narrative"]
    assert "2026-07-19" in body["narrative"]


def test_narrative_seeded_week_mentions_key_facts(client: TestClient) -> None:
    _build_week_fixture(client)

    response = client.get("/reports/narrative", params={"period": "week", "date": "2026-07-15"})

    assert response.status_code == 200
    body = response.json()
    assert body["period"] == "week"
    assert body["start_date"] == "2026-07-13"
    assert body["end_date"] == "2026-07-19"
    assert body["timezone"] == "UTC"

    narrative = body["narrative"]
    highlights = body["highlights"]

    # Total: 240 minutes (4h 0m) across 3 entries.
    assert "4h 0m" in narrative
    assert "3" in narrative

    # Top category: Deep Work, 180 min (3h 0m), 75% share of 240.
    assert "Deep Work" in narrative
    assert "3h 0m" in narrative
    assert "75%" in narrative

    # Second category: Meetings.
    assert "Meetings" in narrative

    # Busiest day: Monday 2026-07-13 (120 min, the largest single day).
    assert "Monday" in narrative
    assert "2026-07-13" in narrative

    # Daily average: 240 minutes across 3 active days = 80 min/day = 1h 20m.
    assert "1h 20m" in narrative

    # Top tag: focus.
    assert "focus" in narrative

    assert isinstance(highlights, list)
    assert len(highlights) > 0
    joined_highlights = " ".join(highlights)
    assert "Deep Work" in joined_highlights
    assert "Monday" in joined_highlights
    assert "focus" in joined_highlights
    assert "Daily average" in joined_highlights


def test_narrative_requires_period_query_param(client: TestClient) -> None:
    response = client.get("/reports/narrative")

    assert response.status_code == 422


def test_narrative_reconciles_with_summary(client: TestClient) -> None:
    _build_week_fixture(client)

    summary = client.get("/reports/summary", params={"period": "week", "date": "2026-07-15"}).json()
    narrative_body = client.get(
        "/reports/narrative", params={"period": "week", "date": "2026-07-15"}
    ).json()

    assert narrative_body["period"] == summary["period"]
    assert narrative_body["start_date"] == summary["start_date"]
    assert narrative_body["end_date"] == summary["end_date"]
    assert narrative_body["timezone"] == summary["timezone"]

    total_hours, total_minutes = divmod(summary["total_minutes"], 60)
    formatted_total = f"{total_hours}h {total_minutes}m"
    assert formatted_total in narrative_body["narrative"]
    assert str(summary["entry_count"]) in narrative_body["narrative"]

    top_category = summary["by_category"][0]
    top_category_name = (
        top_category["category"]["name"] if top_category["category"] else "Uncategorized"
    )
    top_hours, top_minutes = divmod(top_category["total_minutes"], 60)
    formatted_top = f"{top_hours}h {top_minutes}m"
    top_share = round(100 * top_category["total_minutes"] / summary["total_minutes"])

    assert top_category_name in narrative_body["narrative"]
    assert formatted_top in narrative_body["narrative"]
    assert f"{top_share}%" in narrative_body["narrative"]
