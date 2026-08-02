"""Tests for confidence scoring."""

from __future__ import annotations

from pdf_to_epub.classify import PageClass, PageKind
from pdf_to_epub.confidence import score_document, score_page, score_section
from pdf_to_epub.config import Thresholds
from pdf_to_epub.layout import PageLayout

THRESHOLDS = Thresholds()


def _page_class(**overrides: object) -> PageClass:
    base = dict(
        number=1,
        kind=PageKind.BORN_DIGITAL,
        columns=1,
        char_count=500,
        text_area=0.5,
        image_area=0.0,
        word_count=100,
    )
    base.update(overrides)
    return PageClass(**base)  # type: ignore[arg-type]


def _layout(**overrides: object) -> PageLayout:
    base = dict(zones=(), gutters=(), orphan_word_frac=0.0, warnings=())
    base.update(overrides)
    return PageLayout(**base)  # type: ignore[arg-type]


def test_clean_digital_page_scores_full_confidence() -> None:
    score = score_page(
        _page_class(), _layout(), ocr_used=False, table_rejected=False, t=THRESHOLDS
    )
    assert score == 1.0


def test_scanned_without_ocr_is_penalised() -> None:
    score = score_page(
        _page_class(kind=PageKind.SCANNED),
        _layout(),
        ocr_used=False,
        table_rejected=False,
        t=THRESHOLDS,
    )
    assert score == THRESHOLDS.conf_scanned_no_ocr


def test_ocr_used_is_penalised() -> None:
    score = score_page(
        _page_class(), _layout(), ocr_used=True, table_rejected=False, t=THRESHOLDS
    )
    assert score == THRESHOLDS.conf_ocr_used


def test_rejected_table_is_penalised() -> None:
    score = score_page(
        _page_class(), _layout(), ocr_used=False, table_rejected=True, t=THRESHOLDS
    )
    assert score == THRESHOLDS.conf_table_rejected


def test_score_is_clamped_to_unit_interval() -> None:
    score = score_page(
        _page_class(kind=PageKind.SCANNED, char_count=0),
        _layout(orphan_word_frac=0.9),
        ocr_used=True,
        table_rejected=True,
        t=THRESHOLDS,
    )
    assert 0.0 <= score <= 1.0


def test_score_section_is_character_weighted() -> None:
    page_scores = {1: 1.0, 2: 0.5}
    char_counts = {1: 100, 2: 100}
    score = score_section(
        page_scores, [1, 2], char_counts, heading_from_outline=True, t=THRESHOLDS
    )
    assert score == 0.75


def test_score_section_penalised_without_outline_heading() -> None:
    page_scores = {1: 1.0}
    char_counts = {1: 100}
    with_outline = score_section(
        page_scores, [1], char_counts, heading_from_outline=True, t=THRESHOLDS
    )
    without_outline = score_section(
        page_scores, [1], char_counts, heading_from_outline=False, t=THRESHOLDS
    )
    assert without_outline < with_outline


def test_score_document_is_character_weighted() -> None:
    score = score_document([(1.0, 100), (0.0, 100)])
    assert score == 0.5


def test_score_document_empty_defaults_to_one() -> None:
    assert score_document([]) == 1.0
