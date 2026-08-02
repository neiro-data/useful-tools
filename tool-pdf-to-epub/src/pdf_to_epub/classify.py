"""Page and document kind classification. Pure, stdlib-only."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from pdf_to_epub.config import Thresholds
from pdf_to_epub.layout import detect_columns
from pdf_to_epub.pdf_source import PageRaw


class PageKind(StrEnum):
    BORN_DIGITAL = "born_digital"
    SCANNED = "scanned"
    EMPTY = "empty"


@dataclass(frozen=True)
class PageClass:
    number: int
    kind: PageKind
    columns: int
    char_count: int
    text_area: float
    image_area: float
    word_count: int


@dataclass(frozen=True)
class DocClass:
    kind: Literal["scanned", "born_digital", "mixed"]
    columns: int


def classify_page(page: PageRaw, t: Thresholds) -> PageClass:
    """Classify a single page as scanned, born-digital, or empty."""
    if page.char_count < t.scanned_max_chars and page.image_area > t.scanned_min_image_area:
        kind = PageKind.SCANNED
    elif page.char_count >= t.digital_min_chars and page.text_area >= t.digital_min_text_area:
        kind = PageKind.BORN_DIGITAL
    else:
        kind = PageKind.EMPTY

    word_count = len(page.words)
    columns = 1
    if word_count >= t.column_vote_min_words:
        result = detect_columns(page.words, page.width, page.height, t)
        columns = len(result.gutters) + 1

    return PageClass(
        number=page.number,
        kind=kind,
        columns=columns,
        char_count=page.char_count,
        text_area=page.text_area,
        image_area=page.image_area,
        word_count=word_count,
    )


def classify_document(pages: Sequence[PageClass], t: Thresholds) -> DocClass:
    """Classify the whole document's kind and modal column count."""
    non_empty = [p for p in pages if p.kind != PageKind.EMPTY]
    if non_empty:
        scanned_frac = sum(1 for p in non_empty if p.kind == PageKind.SCANNED) / len(non_empty)
        digital_frac = sum(1 for p in non_empty if p.kind == PageKind.BORN_DIGITAL) / len(non_empty)
    else:
        scanned_frac = digital_frac = 0.0

    kind: Literal["scanned", "born_digital", "mixed"]
    if scanned_frac >= t.doc_kind_majority:
        kind = "scanned"
    elif digital_frac >= t.doc_kind_majority:
        kind = "born_digital"
    else:
        kind = "mixed"

    voting_pages = [p for p in pages if p.word_count >= t.column_vote_min_words]
    column_votes = Counter(p.columns for p in voting_pages)
    columns = column_votes.most_common(1)[0][0] if column_votes else 1

    return DocClass(kind=kind, columns=columns)
