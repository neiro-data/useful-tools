"""Tests for reading-order reconstruction: paragraphs, running heads, joining."""

from __future__ import annotations

from pathlib import Path

from pdf_to_epub import pdf_source
from pdf_to_epub.config import Thresholds
from pdf_to_epub.layout import Zone, detect_columns, segment_zones
from pdf_to_epub.reconstruct import (
    Block,
    _join_lines,
    _zone_blocks,
    join_document,
    page_blocks,
    strip_running_heads,
)
from tests.fixtures import make_pdfs

THRESHOLDS = Thresholds()


def _build_blocks(pdf_path: Path) -> list[tuple[pdf_source.PageRaw, tuple[Block, ...]]]:
    pages = pdf_source.load_pages(pdf_path)
    result = []
    for page in pages:
        gutters = detect_columns(page.words, page.width, page.height, THRESHOLDS).gutters
        layout = segment_zones(page.words, gutters, page.width, page.height, THRESHOLDS)
        result.append((page, page_blocks(layout, page, THRESHOLDS)))
    return result


def test_two_column_reading_order_no_interleaving(tmp_path: Path) -> None:
    pdf_path = make_pdfs.make_two_column(tmp_path, pages=1)
    per_page = _build_blocks(pdf_path)
    doc_blocks = join_document(per_page)
    full_text = " ".join(b.text for b in doc_blocks)

    left0 = make_pdfs._LEFT_SENTENCES[0]
    right0 = make_pdfs._RIGHT_SENTENCES[0]
    left_last = make_pdfs._LEFT_SENTENCES[-1]

    assert left0 in full_text
    assert right0 in full_text
    assert full_text.index(left0) < full_text.index(right0)
    # The full left-column sentence appears intact before any right-column sentence.
    assert full_text.index(left_last) < full_text.index(right0)


def test_full_width_title_band_ordered_before_columns(tmp_path: Path) -> None:
    pdf_path = make_pdfs.make_two_column_with_bands(tmp_path)
    per_page = _build_blocks(pdf_path)
    doc_blocks = join_document(per_page)
    full_text = " ".join(b.text for b in doc_blocks)

    title_pos = full_text.index("Complete History")
    left_pos = full_text.index(make_pdfs._LEFT_SENTENCES[0])
    right_pos = full_text.index(make_pdfs._RIGHT_SENTENCES[0])

    assert title_pos < left_pos
    assert title_pos < right_pos


def test_running_heads_and_page_numbers_are_stripped(tmp_path: Path) -> None:
    base_pdf = make_pdfs.make_single_column(tmp_path, pages=5)
    pdf_path = make_pdfs.add_running_head(base_pdf, tmp_path / "rh.pdf")

    per_page = _build_blocks(pdf_path)
    stripped = strip_running_heads(per_page, THRESHOLDS)

    for page, blocks in stripped:
        for block in blocks:
            assert "Valley Chronicles" not in block.text
            assert block.text.strip() != str(page.number)


def test_hyphenated_word_rejoined_without_hyphen() -> None:
    assert _join_lines("a hyphen-", "ated word") == "a hyphenated word"


def _tied_font_words(font_order: list[str]) -> tuple[pdf_source.Word, ...]:
    words = []
    for i, font in enumerate(font_order):
        y = 72.0 + i * 12.0
        words.append(
            pdf_source.Word(
                text=f"word{i}",
                x0=72.0,
                y0=y,
                x1=100.0,
                y1=y + 10.0,
                font=font,
                size=10.0,
                bold=False,
            )
        )
    return tuple(words)


def test_font_key_tie_break_is_deterministic_regardless_of_insertion_order() -> None:
    zone_a = Zone(bbox=(0.0, 0.0, 200.0, 200.0), column_idx=0, band_idx=0,
                   words=_tied_font_words(["Arial", "Arial", "Arial", "Times", "Times", "Times"]))
    zone_b = Zone(bbox=(0.0, 0.0, 200.0, 200.0), column_idx=0, band_idx=0,
                   words=_tied_font_words(["Times", "Times", "Times", "Arial", "Arial", "Arial"]))

    blocks_a = _zone_blocks(zone_a, page_number=1, t=THRESHOLDS)
    blocks_b = _zone_blocks(zone_b, page_number=1, t=THRESHOLDS)

    assert blocks_a and blocks_b
    assert blocks_a[0].font_key == blocks_b[0].font_key
    assert blocks_a[0].font_key == ("Arial", 10.0)


def test_hyphen_after_uppercase_letter_is_kept() -> None:
    # The character immediately before the hyphen is uppercase, so the hyphen is kept.
    assert _join_lines("a US-", "based company") == "a US-based company"
