"""Tests for the ``/exports`` endpoints. See ``app/routers/exports.py``."""

import csv
import io
import re

import pytest
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
    assert "background-color: #2f5bd7" in body
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
    assert "| Category | Color | Time | % | Bar |" in body
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


def test_export_report_pdf_non_latin1_category_referenced_in_narrative_does_not_500(
    client: TestClient,
) -> None:
    """Extends the regression above: the narrative/highlights (``build_narrative``) also embed
    category names, and are rendered into the PDF's "Summary" card -- a non-Latin-1 category name
    referenced there must not crash the PDF renderer either."""
    emoji_category_id = _make_category(client, "Café ☕")
    _make_entry(
        client,
        "Entry",
        "2026-07-15T10:00:00+00:00",
        "2026-07-15T14:00:00+00:00",
        category_id=emoji_category_id,
    )

    pdf_response = client.get(
        "/exports/report.pdf", params={"period": "week", "date": "2026-07-15"}
    )
    assert pdf_response.status_code == 200
    assert pdf_response.content.startswith(PDF_MAGIC_HEADER)

    html_response = client.get(
        "/exports/report.html", params={"period": "week", "date": "2026-07-15"}
    )
    assert "Café ☕" in html_response.text


def test_export_report_pdf_card_spanning_page_break_draws_no_negative_height_rect(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression test: ``_pdf_card`` used to draw its border using the recorded start/end Y
    regardless of page, so a card whose content spans a page break (e.g. the "Entries per week"
    card's day table on a quarter report) got a *negative* height and drew a stray full-page
    border box. Build a quarter report with enough entries to force the day table across
    multiple PDF pages, and assert every ``FPDF.rect`` call has a strictly positive height."""
    from datetime import date, timedelta

    from fpdf import FPDF

    category_id = _make_category(client, "Deep Work")
    quarter_start = date(2026, 1, 1)
    for offset in range(90):
        entry_date = (quarter_start + timedelta(days=offset)).isoformat()
        _make_entry(
            client,
            f"Entry {offset}",
            f"{entry_date}T09:00:00+00:00",
            f"{entry_date}T10:00:00+00:00",
            category_id=category_id,
        )

    recorded_heights: list[float] = []
    original_rect = FPDF.rect

    def _recording_rect(
        self: FPDF, x: float, y: float, w: float, h: float, *args: object, **kwargs: object
    ) -> object:
        recorded_heights.append(h)
        return original_rect(self, x, y, w, h, *args, **kwargs)

    monkeypatch.setattr(FPDF, "rect", _recording_rect)

    response = client.get("/exports/report.pdf", params={"period": "quarter", "date": "2026-02-15"})

    assert response.status_code == 200
    assert response.content.startswith(PDF_MAGIC_HEADER)
    assert recorded_heights, "expected at least one rect() call while rendering the PDF"
    assert all(h > 0 for h in recorded_heights), f"non-positive rect height(s): {recorded_heights}"


# --- by_category is a report-summary-only field, invisible to every export renderer -----------


def test_export_renderers_ignore_reports_by_category_field(client: TestClient) -> None:
    """`ReportBucketCategorySplit`/`by_category` was added to `ReportDayBreakdown`/
    `ReportWeekBreakdown` for the Reports screen's stacked chart; none of the three export
    renderers (html/md/pdf) reference it, so multi-category data must render identically to a
    single flat category breakdown -- no crash, no stray "by_category" text leaking into output."""
    cat1 = _make_category(client, "Deep Work")
    cat2 = _make_category(client, "Meetings")
    _make_entry(
        client, "A", "2026-07-15T09:00:00+00:00", "2026-07-15T10:00:00+00:00", category_id=cat1
    )
    _make_entry(
        client, "B", "2026-07-15T11:00:00+00:00", "2026-07-15T11:30:00+00:00", category_id=cat2
    )

    html_response = client.get(
        "/exports/report.html", params={"period": "week", "date": "2026-07-15"}
    )
    assert html_response.status_code == 200
    assert "by_category" not in html_response.text
    assert "Deep Work" in html_response.text
    assert "Meetings" in html_response.text

    md_response = client.get("/exports/report.md", params={"period": "week", "date": "2026-07-15"})
    assert md_response.status_code == 200
    assert "by_category" not in md_response.text

    pdf_response = client.get(
        "/exports/report.pdf", params={"period": "week", "date": "2026-07-15"}
    )
    assert pdf_response.status_code == 200
    assert pdf_response.content.startswith(PDF_MAGIC_HEADER)


# --- narrative parity across formats -----------------------------------------------------------


def test_export_report_narrative_and_highlight_appear_in_all_three_formats(
    client: TestClient,
) -> None:
    category_id = _make_category(client, "Deep Work")
    _make_entry(
        client,
        "Entry",
        "2026-07-15T10:00:00+00:00",
        "2026-07-15T14:00:00+00:00",
        category_id=category_id,
    )

    html_response = client.get(
        "/exports/report.html", params={"period": "week", "date": "2026-07-15"}
    )
    md_response = client.get("/exports/report.md", params={"period": "week", "date": "2026-07-15"})
    pdf_response = client.get(
        "/exports/report.pdf", params={"period": "week", "date": "2026-07-15"}
    )
    assert html_response.status_code == md_response.status_code == pdf_response.status_code == 200

    # "Deep Work" is the only category, so it's the top-category highlight and appears in the
    # narrative sentence; assert both the highlight text and narrative/summary section show up in
    # HTML and Markdown. PDF text isn't trivially extractable here, so we assert it renders
    # successfully with non-trivial content using the same summary/narrative inputs.
    assert "Deep Work" in html_response.text
    assert "Summary" in html_response.text
    assert "Deep Work" in md_response.text
    assert "## Summary" in md_response.text
    assert pdf_response.content.startswith(PDF_MAGIC_HEADER)
    assert len(pdf_response.content) > 500


# --- category color resolution, end-to-end -------------------------------------------------


def test_export_report_html_category_color_resolves_named_palette_key(client: TestClient) -> None:
    response = client.post("/categories", json={"name": "Deep Work", "color": "blue"})
    category_id = response.json()["id"]
    _make_entry(
        client,
        "Entry",
        "2026-07-15T10:00:00+00:00",
        "2026-07-15T11:00:00+00:00",
        category_id=category_id,
    )

    html_response = client.get(
        "/exports/report.html", params={"period": "week", "date": "2026-07-15"}
    )

    assert "#3457c4" in html_response.text


@pytest.mark.parametrize("color", [None, "bogus"])
def test_export_report_html_category_color_falls_back_to_slate(
    client: TestClient, color: str | None
) -> None:
    payload: dict[str, str] = {"name": "Deep Work"}
    if color is not None:
        payload["color"] = color
    response = client.post("/categories", json=payload)
    category_id = response.json()["id"]
    _make_entry(
        client,
        "Entry",
        "2026-07-15T10:00:00+00:00",
        "2026-07-15T11:00:00+00:00",
        category_id=category_id,
    )

    html_response = client.get(
        "/exports/report.html", params={"period": "week", "date": "2026-07-15"}
    )

    assert "#5b6472" in html_response.text


def test_export_report_html_category_color_passes_through_raw_hex(client: TestClient) -> None:
    response = client.post("/categories", json={"name": "Deep Work", "color": "#ABC"})
    category_id = response.json()["id"]
    _make_entry(
        client,
        "Entry",
        "2026-07-15T10:00:00+00:00",
        "2026-07-15T11:00:00+00:00",
        category_id=category_id,
    )

    html_response = client.get(
        "/exports/report.html", params={"period": "week", "date": "2026-07-15"}
    )

    assert "#aabbcc" in html_response.text.lower()


# --- segmented-bar widths ------------------------------------------------------------------


def test_export_report_html_segmented_bar_widths_sum_to_about_100_percent(
    client: TestClient,
) -> None:
    cat1 = _make_category(client, "Dominant")
    cat2 = _make_category(client, "Tiny")
    _make_entry(
        client, "Big", "2026-07-15T08:00:00+00:00", "2026-07-15T23:30:00+00:00", category_id=cat1
    )
    _make_entry(
        client,
        "Small",
        "2026-07-16T08:00:00+00:00",
        "2026-07-16T08:01:00+00:00",
        category_id=cat2,
    )

    response = client.get("/exports/report.html", params={"period": "week", "date": "2026-07-15"})

    assert response.status_code == 200
    body = response.text
    category_section = body.split("By category")[1].split("By tag")[0]
    widths = [int(w) for w in re.findall(r'width="(\d+)%"', category_section)]
    assert widths, "expected at least one segmented-bar width cell"
    # Allow rounding slack: each of N segments can be off by up to 1% from flooring/rounding.
    assert abs(sum(widths) - 100) <= len(widths)


def test_export_report_html_tiny_segment_does_not_collapse_to_zero_width(
    client: TestClient,
) -> None:
    cat1 = _make_category(client, "Dominant")
    cat2 = _make_category(client, "Tiny")
    _make_entry(
        client, "Big", "2026-07-15T00:00:00+00:00", "2026-07-15T23:00:00+00:00", category_id=cat1
    )
    _make_entry(
        client,
        "Small",
        "2026-07-16T08:00:00+00:00",
        "2026-07-16T08:01:00+00:00",
        category_id=cat2,
    )

    response = client.get("/exports/report.html", params={"period": "week", "date": "2026-07-15"})

    assert response.status_code == 200
    body = response.text
    category_section = body.split("By category")[1].split("By tag")[0]
    widths = [int(w) for w in re.findall(r'width="(\d+)%"', category_section)]
    # "Tiny" is far under 1% of the total, but a nonzero-minutes segment is floored at 1% width.
    assert min(widths) >= 1


# --- section order -------------------------------------------------------------------------


def test_export_report_html_section_order(client: TestClient) -> None:
    category_id = _make_category(client, "Deep Work")
    _make_entry(
        client,
        "Entry",
        "2026-07-15T10:00:00+00:00",
        "2026-07-15T11:00:00+00:00",
        category_id=category_id,
    )

    response = client.get("/exports/report.html", params={"period": "week", "date": "2026-07-15"})

    body = response.text
    assert body.index("By category") < body.index("By tag") < body.index("Summary")


def test_export_report_md_section_order(client: TestClient) -> None:
    category_id = _make_category(client, "Deep Work")
    _make_entry(
        client,
        "Entry",
        "2026-07-15T10:00:00+00:00",
        "2026-07-15T11:00:00+00:00",
        category_id=category_id,
    )

    response = client.get("/exports/report.md", params={"period": "week", "date": "2026-07-15"})

    body = response.text
    assert body.index("By category") < body.index("By tag") < body.index("## Summary")


# --- markdown has no raw HTML, and correctly escapes "|" in table cells --------------------


def test_export_report_md_contains_no_raw_html_tags(client: TestClient) -> None:
    category_id = _make_category(client, "Deep Work")
    _make_entry(
        client,
        "Entry",
        "2026-07-15T10:00:00+00:00",
        "2026-07-15T11:00:00+00:00",
        category_id=category_id,
    )

    response = client.get("/exports/report.md", params={"period": "week", "date": "2026-07-15"})

    body = response.text
    assert re.search(r"<[a-zA-Z][^>]*>", body) is None


def test_export_report_md_table_survives_pipe_in_category_name(client: TestClient) -> None:
    category_id = _make_category(client, "Foo | Bar")
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
    assert "Foo \\| Bar" in body
    category_section = body.split("## By category")[1].split("## By tag")[0]
    data_rows = [
        line
        for line in category_section.splitlines()
        if line.startswith("| ") and "---" not in line and "Category" not in line
    ]
    assert len(data_rows) == 1


# --- regression guard: entries.csv and backup are unaffected --------------------------------


def test_export_entries_csv_regression_headers_and_content_type_unchanged(
    client: TestClient,
) -> None:
    category_id = _make_category(client, "Deep Work")
    tag_id = _make_tag(client, "focus")
    _make_entry(
        client,
        "Regression entry",
        "2026-07-13T10:00:00+00:00",
        "2026-07-13T11:00:00+00:00",
        category_id=category_id,
        tag_ids=[tag_id],
    )

    response = client.get("/exports/entries.csv")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    content_disposition = response.headers["content-disposition"]
    assert content_disposition.startswith("attachment;")
    assert content_disposition.strip().endswith('.csv"')
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


def test_export_entries_csv_regression_formula_injection_still_quoted(
    client: TestClient,
) -> None:
    entry_id = _make_entry(
        client,
        "=cmd()|'/C calc'!A0",
        "2026-07-13T10:00:00+00:00",
        "2026-07-13T11:00:00+00:00",
    )

    response = client.get("/exports/entries.csv")

    rows = _parse_csv(response.content)
    matching = [row for row in rows if row["id"] == str(entry_id)]
    assert matching[0]["title"] == "'=cmd()|'/C calc'!A0"


def test_export_backup_regression_media_type_and_filename_shape_unchanged(
    client: TestClient,
) -> None:
    _make_category(client, "Deep Work")

    response = client.get("/exports/backup")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/octet-stream"
    content_disposition = response.headers["content-disposition"]
    assert content_disposition.startswith("attachment;")
    assert ".sqlite" in content_disposition
    assert response.content.startswith(SQLITE_MAGIC_HEADER)


# --- Outlook-safety invariants ----------------------------------------------------------------


def test_export_report_html_outlook_safety_no_disallowed_constructs(client: TestClient) -> None:
    category_id = _make_category(client, "Deep Work")
    tag_id = _make_tag(client, "focus")
    _make_entry(
        client,
        "Entry",
        "2026-07-15T10:00:00+00:00",
        "2026-07-15T11:00:00+00:00",
        category_id=category_id,
        tag_ids=[tag_id],
    )

    response = client.get("/exports/report.html", params={"period": "week", "date": "2026-07-15"})

    body = response.text
    assert "<style" not in body
    assert "<svg" not in body
    assert "<script" not in body
    assert "var(" not in body
    body_lower = body.lower()
    for retired_color in ("#4c6ef5", "#37b24d", "#f59f00"):
        assert retired_color not in body_lower
