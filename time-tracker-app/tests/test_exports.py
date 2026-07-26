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
    if category_id is None:
        category_id = _make_category(client, f"Auto category for {title!r}")
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


def test_export_entries_csv_neutralizes_formula_injection(client: TestClient) -> None:
    tag_id = _make_tag(client, "=cmd()|'/C calc'!A0")
    entry_id = _make_entry(
        client,
        "=cmd()|'/C calc'!A0",
        "2026-07-13T10:00:00+00:00",
        "2026-07-13T11:00:00+00:00",
        tag_ids=[tag_id],
    )
    response = client.patch(f"/entries/{entry_id}", json={"notes": "=SUM(A1:A9)"})
    assert response.status_code == 200

    csv_response = client.get("/exports/entries.csv")

    assert csv_response.status_code == 200
    rows = _parse_csv(csv_response.content)
    matching = [row for row in rows if row["id"] == str(entry_id)]
    assert len(matching) == 1
    row = matching[0]
    assert row["title"] == "'=cmd()|'/C calc'!A0"
    assert row["tags"] == "'=cmd()|'/C calc'!A0"
    assert row["notes"] == "'=SUM(A1:A9)"
    # normal values remain unchanged
    assert row["duration_minutes"] == "60.0" or float(row["duration_minutes"]) == 60


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


def test_export_report_html_invalid_period_is_validation_error(client: TestClient) -> None:
    response = client.get("/exports/report.html", params={"period": "decade"})

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"


# --- report.html bar charts (Outlook-safety + content) ------------------------------------


def test_export_report_html_bar_charts_are_outlook_safe(client: TestClient) -> None:
    """The bar charts must be nested tables with inline styles only -- no <style> block, no
    <svg>, no <script> anywhere, since Outlook strips all three."""
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
    assert "<style" not in body
    assert "<svg" not in body
    assert "<script" not in body
    # Bar chart cells are nested tables with inline style attributes.
    assert "background-color: #4C6EF5" in body
    assert '<table cellpadding="0" cellspacing="0" border="0"' in body


def test_export_report_html_chart_title_is_by_day_for_week_period(client: TestClient) -> None:
    response = client.get("/exports/report.html", params={"period": "week", "date": "2026-07-15"})

    assert response.status_code == 200
    assert "By day" in response.text
    assert "By week" not in response.text


def test_export_report_html_chart_title_is_by_week_for_month_and_quarter(
    client: TestClient,
) -> None:
    month_response = client.get(
        "/exports/report.html", params={"period": "month", "date": "2026-07-15"}
    )
    quarter_response = client.get(
        "/exports/report.html", params={"period": "quarter", "date": "2026-07-15"}
    )

    assert month_response.status_code == 200
    assert quarter_response.status_code == 200
    assert "By week" in month_response.text
    assert "By week" in quarter_response.text


# --- report.md ------------------------------------------------------------------------------


def test_export_report_md_returns_markdown_attachment(client: TestClient) -> None:
    response = client.get("/exports/report.md", params={"period": "week", "date": "2026-07-15"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    content_disposition = response.headers["content-disposition"]
    assert content_disposition.startswith("attachment;")
    assert ".md" in content_disposition


def test_export_report_md_contains_tables_and_block_bars(client: TestClient) -> None:
    category_id = _make_category(client, "Deep Work")
    _make_entry(
        client,
        "Entry",
        "2026-07-15T10:00:00+00:00",
        "2026-07-15T11:00:00+00:00",
        category_id=category_id,
    )

    response = client.get("/exports/report.md", params={"period": "week", "date": "2026-07-15"})

    assert response.status_code == 200
    body = response.text
    assert "| Category | Time | Entries |" in body
    assert "Deep Work" in body
    assert "█" in body or "░" in body


def test_export_report_md_requires_period(client: TestClient) -> None:
    response = client.get("/exports/report.md")

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"


def test_export_report_md_invalid_period_is_validation_error(client: TestClient) -> None:
    response = client.get("/exports/report.md", params={"period": "decade"})

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"


# --- report.pdf -----------------------------------------------------------------------------

PDF_MAGIC_HEADER = b"%PDF"


def test_export_report_pdf_returns_pdf_attachment(client: TestClient) -> None:
    response = client.get("/exports/report.pdf", params={"period": "week", "date": "2026-07-15"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    content_disposition = response.headers["content-disposition"]
    assert content_disposition.startswith("attachment;")
    assert ".pdf" in content_disposition


def test_export_report_pdf_body_starts_with_magic_bytes_and_is_non_trivial(
    client: TestClient,
) -> None:
    category_id = _make_category(client, "Deep Work")
    _make_entry(
        client,
        "Entry",
        "2026-07-15T10:00:00+00:00",
        "2026-07-15T11:00:00+00:00",
        category_id=category_id,
    )

    response = client.get("/exports/report.pdf", params={"period": "month", "date": "2026-07-15"})

    assert response.status_code == 200
    assert response.content.startswith(PDF_MAGIC_HEADER)
    assert len(response.content) > 500


def test_export_report_pdf_requires_period(client: TestClient) -> None:
    response = client.get("/exports/report.pdf")

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"


def test_export_report_pdf_invalid_period_is_validation_error(client: TestClient) -> None:
    response = client.get("/exports/report.pdf", params={"period": "decade"})

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"


def test_export_report_pdf_non_latin1_category_and_tag_names_do_not_500(
    client: TestClient,
) -> None:
    """Regression test: fpdf2's core Helvetica font is Latin-1 only, so a category/tag name with
    e.g. emoji or CJK characters used to crash ``GET /exports/report.pdf`` with
    ``FPDFUnicodeEncodingException``. The PDF renderer now sanitizes free text instead; HTML and
    Markdown are unaffected and must keep the original characters intact."""
    emoji_category_id = _make_category(client, "Café ☕")
    cjk_tag_id = _make_tag(client, "日本語")
    _make_entry(
        client,
        "Entry",
        "2026-07-15T10:00:00+00:00",
        "2026-07-15T11:00:00+00:00",
        category_id=emoji_category_id,
        tag_ids=[cjk_tag_id],
    )

    pdf_response = client.get(
        "/exports/report.pdf", params={"period": "week", "date": "2026-07-15"}
    )
    assert pdf_response.status_code == 200
    assert pdf_response.content.startswith(PDF_MAGIC_HEADER)

    html_response = client.get(
        "/exports/report.html", params={"period": "week", "date": "2026-07-15"}
    )
    assert html_response.status_code == 200
    assert "Café ☕" in html_response.text
    assert "日本語" in html_response.text

    md_response = client.get("/exports/report.md", params={"period": "week", "date": "2026-07-15"})
    assert md_response.status_code == 200
    assert "Café ☕" in md_response.text
    assert "日本語" in md_response.text
