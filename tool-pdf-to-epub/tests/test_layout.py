"""Tests for column/zone layout detection."""

from __future__ import annotations

from pathlib import Path

from pdf_to_epub import pdf_source
from pdf_to_epub.config import Thresholds
from pdf_to_epub.layout import Zone, detect_columns, segment_zones
from tests.fixtures import make_pdfs

THRESHOLDS = Thresholds()


def test_single_column_page_has_no_gutters(tmp_path: Path) -> None:
    pdf_path = make_pdfs.make_single_column(tmp_path, pages=1)
    page = pdf_source.load_pages(pdf_path)[0]

    gutters = detect_columns(page.words, page.width, page.height, THRESHOLDS).gutters

    assert gutters == ()


def test_two_column_page_detects_one_gutter(tmp_path: Path) -> None:
    pdf_path = make_pdfs.make_two_column(tmp_path, pages=1)
    page = pdf_source.load_pages(pdf_path)[0]

    gutters = detect_columns(page.words, page.width, page.height, THRESHOLDS).gutters

    assert len(gutters) == 1
    assert THRESHOLDS.gutter_search_lo * page.width < gutters[0].x0
    assert gutters[0].x1 < THRESHOLDS.gutter_search_hi * page.width


def test_two_column_zones_are_left_then_right(tmp_path: Path) -> None:
    pdf_path = make_pdfs.make_two_column(tmp_path, pages=1)
    page = pdf_source.load_pages(pdf_path)[0]
    gutters = detect_columns(page.words, page.width, page.height, THRESHOLDS).gutters

    layout = segment_zones(page.words, gutters, page.width, page.height, THRESHOLDS)

    columns_in_order = [zone.column_idx for zone in sorted(layout.zones, key=lambda z: z.band_idx)]
    assert columns_in_order == sorted(columns_in_order)
    assert layout.orphan_word_frac <= THRESHOLDS.orphan_word_frac


def test_full_width_title_band_is_separate_zone(tmp_path: Path) -> None:
    pdf_path = make_pdfs.make_two_column_with_bands(tmp_path)
    page = pdf_source.load_pages(pdf_path)[0]
    gutters = detect_columns(page.words, page.width, page.height, THRESHOLDS).gutters

    layout = segment_zones(page.words, gutters, page.width, page.height, THRESHOLDS)

    band_zone_counts: dict[int, list[Zone]] = {}
    for zone in layout.zones:
        band_zone_counts.setdefault(zone.band_idx, []).append(zone)

    # First band should be a single spanning zone containing the title.
    first_band_zones = band_zone_counts[min(band_zone_counts)]
    assert len(first_band_zones) == 1
    title_words = " ".join(w.text for w in first_band_zones[0].words)
    assert "Complete" in title_words
