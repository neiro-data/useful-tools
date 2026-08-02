"""Confidence scoring for pages, sections, and the whole document. Pure, stdlib-only."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from pdf_to_epub.classify import PageClass
from pdf_to_epub.config import Thresholds
from pdf_to_epub.layout import PageLayout

_DEFAULT_THRESHOLDS = Thresholds()


def score_page(
    page_class: PageClass,
    layout: PageLayout,
    *,
    ocr_used: bool,
    table_rejected: bool,
    t: Thresholds,
) -> float:
    """Score one page's trustworthiness in [0.0, 1.0]."""
    score = 1.0

    if page_class.kind == "scanned" and not ocr_used:
        score *= t.conf_scanned_no_ocr
    if ocr_used:
        score *= t.conf_ocr_used
    if any(w.code == "layout.ambiguous_columns" for w in layout.warnings):
        score *= t.conf_ambiguous_columns
    if len(layout.gutters) > t.max_gutters:
        score *= t.conf_too_many_gutters
    if page_class.char_count < t.near_empty_char_count:
        score *= t.conf_near_empty_page
    if table_rejected:
        score *= t.conf_table_rejected
    if layout.orphan_word_frac > t.orphan_word_frac:
        score *= 1.0 - layout.orphan_word_frac

    return max(0.0, min(1.0, score))


def score_section(
    page_scores: Mapping[int, float],
    chapter_pages: Sequence[int],
    char_counts: Mapping[int, int],
    *,
    heading_from_outline: bool,
    t: Thresholds = _DEFAULT_THRESHOLDS,
) -> float:
    """Character-weighted mean of a chapter's page scores."""
    total_chars = 0
    weighted = 0.0
    for page in chapter_pages:
        chars = char_counts.get(page, 0)
        weighted += page_scores.get(page, 1.0) * chars
        total_chars += chars

    score = (weighted / total_chars) if total_chars else 1.0
    if not heading_from_outline:
        score *= t.conf_heading_from_size_heuristic
    return max(0.0, min(1.0, score))


def score_document(chapters: Sequence[tuple[float, int]]) -> float:
    """Character-weighted mean of (score, char_count) pairs across chapters."""
    total_chars = sum(chars for _, chars in chapters)
    if not total_chars:
        return 1.0
    weighted = sum(score * chars for score, chars in chapters)
    return max(0.0, min(1.0, weighted / total_chars))
