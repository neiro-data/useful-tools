"""Tests for page/document classification."""

from __future__ import annotations

from pathlib import Path

from pdf_to_epub import pdf_source
from pdf_to_epub.classify import PageKind, classify_document, classify_page
from pdf_to_epub.config import Thresholds
from tests.fixtures import make_pdfs

THRESHOLDS = Thresholds()


def test_scanned_page_classified_as_scanned(tmp_path: Path) -> None:
    pdf_path = make_pdfs.make_scanned(tmp_path)
    page = pdf_source.load_pages(pdf_path)[0]

    result = classify_page(page, THRESHOLDS)

    assert result.kind == PageKind.SCANNED


def test_born_digital_page_classified_as_born_digital(tmp_path: Path) -> None:
    pdf_path = make_pdfs.make_single_column(tmp_path, pages=1)
    page = pdf_source.load_pages(pdf_path)[0]

    result = classify_page(page, THRESHOLDS)

    assert result.kind == PageKind.BORN_DIGITAL


def test_document_kind_majority_born_digital(tmp_path: Path) -> None:
    pdf_path = make_pdfs.make_single_column(tmp_path, pages=4)
    pages = pdf_source.load_pages(pdf_path)
    page_classes = [classify_page(p, THRESHOLDS) for p in pages]

    doc_class = classify_document(page_classes, THRESHOLDS)

    assert doc_class.kind == "born_digital"


def test_document_column_vote_two_column(tmp_path: Path) -> None:
    pdf_path = make_pdfs.make_two_column(tmp_path, pages=2)
    pages = pdf_source.load_pages(pdf_path)
    page_classes = [classify_page(p, THRESHOLDS) for p in pages]

    doc_class = classify_document(page_classes, THRESHOLDS)

    assert doc_class.columns == 2
