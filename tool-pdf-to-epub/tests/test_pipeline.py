"""Tests for the end-to-end build orchestration."""

from __future__ import annotations

from pathlib import Path

import pdfplumber
import pytest

from pdf_to_epub.config import BuildConfig
from pdf_to_epub.pipeline import build_book_model, classify_document_report, inspect_document
from tests.fixtures import make_pdfs


def test_build_book_model_single_column(tmp_path: Path) -> None:
    pdf_path = make_pdfs.make_single_column(tmp_path, pages=2)
    config = BuildConfig(input_path=pdf_path, output_path=tmp_path / "out.epub")

    book = build_book_model(config)

    assert book.chapters
    assert book.metadata.modified == "1970-01-01T00:00:00Z"
    assert not any(w.severity == "error" for w in book.warnings)


def test_build_book_model_is_deterministic(tmp_path: Path) -> None:
    pdf_path = make_pdfs.make_single_column(tmp_path, pages=2)
    config = BuildConfig(input_path=pdf_path, output_path=tmp_path / "out.epub")

    book_a = build_book_model(config)
    book_b = build_book_model(config)

    assert book_a.metadata.identifier == book_b.metadata.identifier
    assert book_a.chapters == book_b.chapters


def test_scanned_without_ocr_records_error_warning(tmp_path: Path) -> None:
    pdf_path = make_pdfs.make_scanned(tmp_path)
    config = BuildConfig(input_path=pdf_path, output_path=tmp_path / "out.epub")

    book = build_book_model(config)

    assert any(
        w.code == "pdf.scanned_without_ocr" and w.severity == "error" for w in book.warnings
    )


def test_inspect_document_reports_pages_and_tables(tmp_path: Path) -> None:
    pdf_path = make_pdfs.make_table_page(tmp_path)
    config = BuildConfig(input_path=pdf_path, output_path=tmp_path / "out.epub")

    report = inspect_document(config)

    assert report.pages
    assert report.tables_detected >= 0


def test_classify_document_report(tmp_path: Path) -> None:
    pdf_path = make_pdfs.make_scanned(tmp_path)
    config = BuildConfig(input_path=pdf_path, output_path=tmp_path / "out.epub")

    report = classify_document_report(config)

    assert report.doc.kind == "scanned"
    assert len(report.pages) == 1


def test_table_extraction_opens_pdf_at_most_once_per_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf_path = make_pdfs.make_single_column(tmp_path, pages=5)
    config = BuildConfig(input_path=pdf_path, output_path=tmp_path / "out.epub")

    calls = {"count": 0}
    real_open = pdfplumber.open

    def counting_open(path: object) -> object:
        calls["count"] += 1
        return real_open(path)  # type: ignore[arg-type]

    monkeypatch.setattr("pdf_to_epub.plumber_source.pdfplumber.open", counting_open)

    build_book_model(config)

    assert calls["count"] <= 1


def test_no_tables_flag_never_opens_pdfplumber(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf_path = make_pdfs.make_single_column(tmp_path, pages=5)
    config = BuildConfig(
        input_path=pdf_path, output_path=tmp_path / "out.epub", include_tables=False
    )

    calls = {"count": 0}

    def counting_open(*args: object, **kwargs: object) -> object:
        calls["count"] += 1
        raise AssertionError("pdfplumber.open must not be called with tables disabled")

    monkeypatch.setattr("pdf_to_epub.plumber_source.pdfplumber.open", counting_open)

    build_book_model(config)

    assert calls["count"] == 0
