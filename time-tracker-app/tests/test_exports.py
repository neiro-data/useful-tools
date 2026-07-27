"""Tests for the ``/exports`` endpoints. See ``app/routers/exports.py``."""

import csv
import io
import re
from html import escape

import pytest
from fastapi.testclient import TestClient

from app.report_theme import CAT_PALETTE

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


def test_export_report_html_has_no_data_tables(client: TestClient) -> None:
    """The Reports page has no tables; the segmented-breakdown legends carry the numbers instead,
    so the HTML export must not render any ``<table>`` markup."""
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
    assert "<table" not in response.text


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


# --- report.html charts (self-containment + content) --------------------------------------


def test_export_report_html_stacked_chart_title_is_hours_by_category_for_all_periods(
    client: TestClient,
) -> None:
    """The stacked chart's title is now the same regardless of bucket granularity (day vs. week),
    unlike the retired horizontal bar chart's "By day"/"By week" titles."""
    week_response = client.get(
        "/exports/report.html", params={"period": "week", "date": "2026-07-15"}
    )
    month_response = client.get(
        "/exports/report.html", params={"period": "month", "date": "2026-07-15"}
    )
    quarter_response = client.get(
        "/exports/report.html", params={"period": "quarter", "date": "2026-07-15"}
    )

    assert week_response.status_code == 200
    assert month_response.status_code == 200
    assert quarter_response.status_code == 200
    assert "Hours by category" in week_response.text
    assert "Hours by category" in month_response.text
    assert "Hours by category" in quarter_response.text


def test_export_report_html_count_chart_title_is_per_day_for_week_period(
    client: TestClient,
) -> None:
    response = client.get("/exports/report.html", params={"period": "week", "date": "2026-07-15"})

    assert response.status_code == 200
    assert "Entries per day" in response.text
    assert "Entries per week" not in response.text


def test_export_report_html_count_chart_title_is_per_week_for_month_and_quarter(
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
    assert "Entries per week" in month_response.text
    assert "Entries per week" in quarter_response.text


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


# --- segmented-bar proportions (flex-based markup) ------------------------------------------


def test_export_report_html_segmented_bar_flex_grow_values_sum_to_about_100(
    client: TestClient,
) -> None:
    """The segmented bar is now a flex row (``flex-grow: N`` per segment div, rounded percent),
    not an HTML ``width="N%"`` attribute -- assert the flex-grow values still sum to ~100."""
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
    bar_section = category_section.split('<div class="seg-bar">')[1].split("</div>")[0]
    values = [int(v) for v in re.findall(r"flex-grow: (\d+)", bar_section)]
    assert values, "expected at least one segmented-bar flex-grow value"
    # Allow rounding slack: each of N segments can be off by up to 1% from flooring/rounding.
    assert abs(sum(values) - 100) <= len(values)


def test_export_report_html_tiny_segment_does_not_collapse_to_zero_flex_grow(
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
    bar_section = category_section.split('<div class="seg-bar">')[1].split("</div>")[0]
    values = [int(v) for v in re.findall(r"flex-grow: (\d+)", bar_section)]
    # "Tiny" is far under 1% of the total, but a nonzero-minutes segment is floored at flex-grow 1.
    assert min(values) >= 1


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


# --- self-contained-document invariants (no Outlook constraint anymore) -----------------------


def test_export_report_html_document_is_self_contained(client: TestClient) -> None:
    """The HTML export intentionally uses ``<style>``/``<svg>`` (the Outlook-compatibility
    constraint was dropped by explicit decision), but the document must still be fully
    self-contained: no external stylesheet/font/image/script URLs, no remote ``src``/``href``, and
    no ``<script>`` tag."""
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
    assert "<script" not in body
    assert "<link" not in body
    assert re.search(r'(?:src|href)\s*=\s*["\']https?://', body) is None
    assert "@import" not in body
    assert "var(" not in body


# --- stacked "Hours by category" chart -------------------------------------------------------


def test_export_report_html_stacked_chart_segments_use_resolved_category_colors_and_order(
    client: TestClient,
) -> None:
    """Each bucket's stack segments must carry the resolved hex color for their category, in the
    same order as ``summary.by_category`` (total minutes descending)."""
    dominant = client.post("/categories", json={"name": "Dominant", "color": "blue"}).json()["id"]
    minor = client.post("/categories", json={"name": "Minor", "color": "green"}).json()["id"]
    _make_entry(
        client,
        "Big",
        "2026-07-15T08:00:00+00:00",
        "2026-07-15T12:00:00+00:00",
        category_id=dominant,
    )
    _make_entry(
        client,
        "Small",
        "2026-07-15T13:00:00+00:00",
        "2026-07-15T13:30:00+00:00",
        category_id=minor,
    )

    response = client.get("/exports/report.html", params={"period": "week", "date": "2026-07-15"})

    assert response.status_code == 200
    body = response.text
    chart_section = body.split("Hours by category")[1].split("Entries per")[0]
    blue_index = chart_section.index(CAT_PALETTE["blue"])
    green_index = chart_section.index(CAT_PALETTE["green"])
    assert blue_index < green_index


def test_export_report_html_stacked_chart_week_period_has_seven_zero_filled_columns(
    client: TestClient,
) -> None:
    """A ``week`` period must render 7 day columns even though only some days have entries --
    ``by_day`` is sparse from the API and the exporter zero-fills it, mirroring the app."""
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
    chart_section = body.split("Hours by category")[1].split("Entries per")[0]
    assert chart_section.count('<div class="column"') == 7


def test_export_report_html_stacked_chart_month_period_buckets_by_week(
    client: TestClient,
) -> None:
    """``month``/``quarter`` periods bucket by week, not by day -- the other branch of every chart
    helper."""
    category_id = _make_category(client, "Deep Work")
    _make_entry(
        client,
        "Entry",
        "2026-07-15T10:00:00+00:00",
        "2026-07-15T11:00:00+00:00",
        category_id=category_id,
    )

    response = client.get("/exports/report.html", params={"period": "month", "date": "2026-07-15"})

    assert response.status_code == 200
    body = response.text
    chart_section = body.split("Hours by category")[1].split("Entries per")[0]
    count_chart_section = body.split("Entries per")[1]
    column_count = chart_section.count('<div class="column"')
    marker_count = count_chart_section.count('class="marker"')
    assert column_count != 7
    assert 1 <= column_count <= 6
    assert column_count == marker_count


# --- "Entries per day/week" line chart ---------------------------------------------------------


def test_export_report_html_count_chart_point_count_matches_zero_filled_days(
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

    response = client.get("/exports/report.html", params={"period": "week", "date": "2026-07-15"})

    assert response.status_code == 200
    count_chart_section = response.text.split("Entries per")[1]
    assert count_chart_section.count('class="marker"') == 7


# --- edge cases: zero entries, zero-minute bucket, single bucket, special characters -----------


@pytest.mark.parametrize("period", ["week", "month", "quarter"])
def test_export_report_html_zero_entries_renders_without_error(
    client: TestClient, period: str
) -> None:
    response = client.get("/exports/report.html", params={"period": period, "date": "2026-07-15"})

    assert response.status_code == 200
    assert "No entries." in response.text
    assert "<table" not in response.text


@pytest.mark.parametrize("period", ["week", "month", "quarter"])
def test_export_report_md_zero_entries_renders_without_error(
    client: TestClient, period: str
) -> None:
    response = client.get("/exports/report.md", params={"period": period, "date": "2026-07-15"})

    assert response.status_code == 200
    assert "No entries." in response.text


@pytest.mark.parametrize("period", ["week", "month", "quarter"])
def test_export_report_pdf_zero_entries_renders_without_raising(
    client: TestClient, period: str
) -> None:
    response = client.get("/exports/report.pdf", params={"period": period, "date": "2026-07-15"})

    assert response.status_code == 200
    assert response.content.startswith(PDF_MAGIC_HEADER)


def test_export_report_html_zero_total_bucket_does_not_raise_zero_division(
    client: TestClient,
) -> None:
    """A single entry means most buckets in the period have zero total minutes -- the stacked
    chart's ``stack_height`` and per-segment ``flex-grow`` math must not divide by zero."""
    category_id = _make_category(client, "Deep Work")
    _make_entry(
        client,
        "Only entry",
        "2026-01-01T10:00:00+00:00",
        "2026-01-01T11:00:00+00:00",
        category_id=category_id,
    )

    response = client.get(
        "/exports/report.html", params={"period": "quarter", "date": "2026-01-15"}
    )

    assert response.status_code == 200


def test_export_report_pdf_zero_total_bucket_does_not_raise_zero_division(
    client: TestClient,
) -> None:
    category_id = _make_category(client, "Deep Work")
    _make_entry(
        client,
        "Only entry",
        "2026-01-01T10:00:00+00:00",
        "2026-01-01T11:00:00+00:00",
        category_id=category_id,
    )

    response = client.get("/exports/report.pdf", params={"period": "quarter", "date": "2026-01-15"})

    assert response.status_code == 200
    assert response.content.startswith(PDF_MAGIC_HEADER)


def test_export_report_html_single_bucket_does_not_raise(client: TestClient) -> None:
    """A single-day ``week`` report still has 7 zero-filled buckets, but a narrow custom range
    isn't available here -- exercise the N=1 polyline branch indirectly via a week with all
    activity concentrated in one bucket to ensure the ``len(coords) > 1`` guard is safe either
    way."""
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


@pytest.mark.parametrize(
    ("category_name", "tag_name"),
    [
        ('<b>Deep</b> & "Work" | Tag', "<i>focus</i>"),
        ("Café ☕ 日本語", "日本語タグ"),
    ],
)
def test_export_report_html_escapes_special_characters_in_names(
    client: TestClient, category_name: str, tag_name: str
) -> None:
    category_id = _make_category(client, category_name)
    tag_id = _make_tag(client, tag_name)
    _make_entry(
        client,
        "Entry",
        "2026-07-15T10:00:00+00:00",
        "2026-07-15T11:00:00+00:00",
        category_id=category_id,
        tag_ids=[tag_id],
    )

    response = client.get("/exports/report.html", params={"period": "week", "date": "2026-07-15"})

    assert response.status_code == 200
    body = response.text
    assert "<b>" not in body
    assert "<i>" not in body
    assert escape(category_name) in body
    assert escape(f"#{tag_name}") in body


@pytest.mark.parametrize(
    ("category_name", "tag_name"),
    [
        ("Foo | Bar & <Baz>", "Tag | Pipe"),
        ("Café ☕ 日本語", "日本語タグ"),
    ],
)
def test_export_report_md_escapes_pipes_in_names(
    client: TestClient, category_name: str, tag_name: str
) -> None:
    category_id = _make_category(client, category_name)
    tag_id = _make_tag(client, tag_name)
    _make_entry(
        client,
        "Entry",
        "2026-07-15T10:00:00+00:00",
        "2026-07-15T11:00:00+00:00",
        category_id=category_id,
        tag_ids=[tag_id],
    )

    response = client.get("/exports/report.md", params={"period": "week", "date": "2026-07-15"})

    assert response.status_code == 200
    body = response.text
    escaped_name = category_name.replace("|", "\\|")
    assert escaped_name in body


@pytest.mark.parametrize(
    ("category_name", "tag_name"),
    [
        ('<b>Deep</b> & "Work" | Tag', "<i>focus</i>"),
        ("Café ☕ 日本語", "日本語タグ"),
    ],
)
def test_export_report_pdf_special_characters_degrade_via_pdf_safe_without_raising(
    client: TestClient, category_name: str, tag_name: str
) -> None:
    """PDF rendering must degrade non-Latin-1 (and any otherwise problematic) characters via
    ``_pdf_safe`` rather than raise ``FPDFUnicodeEncodingException`` or any other error."""
    category_id = _make_category(client, category_name)
    tag_id = _make_tag(client, tag_name)
    _make_entry(
        client,
        "Entry",
        "2026-07-15T10:00:00+00:00",
        "2026-07-15T11:00:00+00:00",
        category_id=category_id,
        tag_ids=[tag_id],
    )

    response = client.get("/exports/report.pdf", params={"period": "week", "date": "2026-07-15"})

    assert response.status_code == 200
    assert response.content.startswith(PDF_MAGIC_HEADER)


# --- code-review regression: tag legend cap, PDF bar overflow, markdown narrative escaping ------


def test_export_report_tag_legend_capped_at_five_with_more_indicator(client: TestClient) -> None:
    """``ReportsPage.tsx`` caps the "By tag" legend at the top 5 (``visibleLimit={5}``) with a
    "+N more tags" line; the exports must match, in all three formats, so a report with many tags
    doesn't dump an unbounded legend (and, in the PDF, doesn't blow the two-column top row's
    height estimate -- see the next test)."""
    category_id = _make_category(client, "Deep Work")
    tag_ids = [_make_tag(client, f"tag{i}") for i in range(8)]
    # Descending durations so segment order (by total_minutes desc) is deterministic: tag0..tag4
    # visible, tag5..tag7 hidden behind "+ 3 more tags".
    for index, tag_id in enumerate(tag_ids):
        minutes = 40 - index * 5
        start_hour = index
        _make_entry(
            client,
            f"Entry {index}",
            f"2026-07-15T{start_hour:02d}:00:00+00:00",
            f"2026-07-15T{start_hour:02d}:{minutes:02d}:00+00:00",
            category_id=category_id,
            tag_ids=[tag_id],
        )

    html_response = client.get(
        "/exports/report.html", params={"period": "week", "date": "2026-07-15"}
    )
    assert html_response.status_code == 200
    html_body = html_response.text
    tag_html_section = html_body.split("By tag")[1].split("Hours by category")[0]
    for index in range(5):
        assert f"tag{index}" in tag_html_section
    for index in range(5, 8):
        assert f"tag{index}" not in tag_html_section
    assert "+ 3 more tags" in tag_html_section

    md_response = client.get("/exports/report.md", params={"period": "week", "date": "2026-07-15"})
    assert md_response.status_code == 200
    md_body = md_response.text
    tag_md_section = md_body.split("## By tag")[1].split("## Hours by category")[0]
    for index in range(5):
        assert f"tag{index}" in tag_md_section
    for index in range(5, 8):
        assert f"tag{index}" not in tag_md_section
    assert "+ 3 more tags" in tag_md_section

    pdf_response = client.get(
        "/exports/report.pdf", params={"period": "week", "date": "2026-07-15"}
    )
    assert pdf_response.status_code == 200
    assert pdf_response.content.startswith(PDF_MAGIC_HEADER)


def test_export_report_pdf_two_column_row_falls_back_to_stacked_when_it_would_overflow(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression test for the silent-truncation bug: with ``auto_page_break`` disabled for the
    two-column top row, content drawn past the physical page bottom used to vanish with no
    exception and no artifact. Enough categories (uncapped, unlike tags) make the "By category"
    breakdown taller than the space actually available for the row, which must now trigger the
    stacked (``_pdf_card``, full-width) fallback instead of drawing side-by-side and silently
    dropping content. Assert every ``rect()`` card border drawn is full content width -- i.e. the
    fallback path, not two half-width cards -- and that the response still renders successfully."""
    from fpdf import FPDF

    category_ids = [_make_category(client, f"Category {i}") for i in range(60)]
    for index, category_id in enumerate(category_ids):
        hour = index % 24
        minute = (index // 24) * 2
        _make_entry(
            client,
            f"Entry {index}",
            f"2026-07-15T{hour:02d}:{minute:02d}:00+00:00",
            f"2026-07-15T{hour:02d}:{minute + 1:02d}:00+00:00",
            category_id=category_id,
        )

    recorded_rects: list[tuple[float, float, float, float]] = []
    original_rect = FPDF.rect

    def _recording_rect(
        self: FPDF, x: float, y: float, w: float, h: float, *args: object, **kwargs: object
    ) -> object:
        recorded_rects.append((x, y, w, h))
        return original_rect(self, x, y, w, h, *args, **kwargs)

    monkeypatch.setattr(FPDF, "rect", _recording_rect)

    response = client.get("/exports/report.pdf", params={"period": "week", "date": "2026-07-15"})

    assert response.status_code == 200
    assert response.content.startswith(PDF_MAGIC_HEADER)
    # Card border rects are drawn with style="D" -- fpdf2 doesn't surface style back to us via
    # this monkeypatch, but a fallback (stacked) card border is always full content width, while a
    # side-by-side card border is always half that (minus the gutter); assert none of the two
    # tallest/first rects drawn is a half-width card border, i.e. the row did NOT draw side by
    # side.
    content_width = 210.0 - 2 * 15.0
    half_width_ish = content_width / 2
    early_widths = [w for _, _, w, h in recorded_rects[:4] if h > 20]
    assert not any(abs(w - half_width_ish) < 1.0 for w in early_widths), (
        f"expected the two-column row to fall back to stacked full-width cards, but found a "
        f"half-width card border among the first rects: {early_widths}"
    )


def test_export_report_pdf_segmented_bar_widths_never_exceed_available_width() -> None:
    """Unit-level regression test for the PDF-only overflow bug: ``max(1.0, ...)`` floors a tiny
    segment's width up but never reclaims the extra from the rest, so the unfloored widths (which
    already sum to exactly ``width``, since percentages sum to 100) could add up to more than
    ``width`` and draw past the card's right edge. ``_pdf_segment_bar_widths`` must keep the total
    at or under ``width`` regardless of how small one segment's share is, while still keeping
    every nonzero segment visible (width > 0)."""
    from app.routers.exports import Segment, _pdf_segment_bar_widths

    width = 84.0
    segments = [
        Segment(label="Dominant", minutes=1430, percent=99.3, color="#111111"),
        Segment(label="Tiny", minutes=10, percent=0.7, color="#222222"),
    ]

    widths = _pdf_segment_bar_widths(segments, width)

    assert sum(widths) <= width + 1e-6
    assert all(w > 0 for w in widths), "a nonzero-minutes segment must stay visible"


def test_export_report_markdown_narrative_escapes_pipe_and_neutralizes_newline(
    client: TestClient,
) -> None:
    """``build_narrative`` interpolates raw category/tag names into ``narrative``/``highlights``,
    which ``_render_report_markdown`` used to write straight into the ``## Summary`` section
    unescaped -- a category name containing ``|`` could corrupt Markdown table-adjacent parsing,
    and an embedded newline could start a new Markdown block (e.g. inject a fake heading) inside
    the Summary section. Both must be neutralized."""
    category_name = "Weird | Name\nInjected # Heading"
    category_id = _make_category(client, category_name)
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
    summary_section = body.split("## Summary", 1)[1]

    assert "Weird \\| Name Injected # Heading" in summary_section
    assert "Weird | Name\nInjected # Heading" not in summary_section
    for line in summary_section.splitlines():
        stripped = line.strip()
        assert not stripped.startswith("# Injected"), (
            f"a raw newline from the category name leaked into a Markdown heading line: {line!r}"
        )
