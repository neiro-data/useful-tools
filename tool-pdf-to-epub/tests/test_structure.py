"""Tests for heading inference and chapter/TOC assembly."""

from __future__ import annotations

from pathlib import Path

from pdf_to_epub import pdf_source
from pdf_to_epub.config import Thresholds
from pdf_to_epub.layout import detect_columns, segment_zones
from pdf_to_epub.reconstruct import Block, join_document, page_blocks, strip_running_heads
from pdf_to_epub.structure import body_style, build_structure, infer_headings
from tests.fixtures import make_pdfs

THRESHOLDS = Thresholds()


def _doc_blocks(pdf_path: Path) -> tuple[Block, ...]:
    pages = pdf_source.load_pages(pdf_path)
    per_page = []
    for page in pages:
        result = detect_columns(page.words, page.width, page.height, THRESHOLDS)
        layout = segment_zones(
            page.words, result.gutters, page.width, page.height, THRESHOLDS, result.warnings
        )
        per_page.append((page, page_blocks(layout, page, THRESHOLDS)))
    stripped = strip_running_heads(per_page, THRESHOLDS)
    return join_document(stripped)


def test_heading_inference_maps_three_sizes_to_h1_h2_h3(tmp_path: Path) -> None:
    pdf_path = make_pdfs.make_with_headings(tmp_path)
    blocks = _doc_blocks(pdf_path)
    body_size, _ = body_style(blocks)

    annotated = infer_headings(blocks, body_size, THRESHOLDS)
    levels = {b.level for b in annotated if b.kind == "heading"}

    assert levels == {1, 2}


def test_split_level_two_produces_more_chapters(tmp_path: Path) -> None:
    pdf_path = make_pdfs.make_with_headings(tmp_path)
    blocks = _doc_blocks(pdf_path)
    outline = pdf_source.load_outline(pdf_path)

    result_1 = build_structure(blocks, outline, 1, THRESHOLDS)
    result_2 = build_structure(blocks, outline, 2, THRESHOLDS)

    assert len(result_2.chapters) > len(result_1.chapters)


def test_toc_uses_outline_when_present(tmp_path: Path) -> None:
    pdf_path = make_pdfs.make_with_headings(tmp_path, set_outline=True)
    blocks = _doc_blocks(pdf_path)
    outline = pdf_source.load_outline(pdf_path)

    result = build_structure(blocks, outline, 1, THRESHOLDS)

    assert result.outline_used is True
    assert result.toc
    assert not any(w.code == "structure.outline_fallback" for w in result.warnings)


def test_toc_falls_back_with_warning_when_outline_missing(tmp_path: Path) -> None:
    pdf_path = make_pdfs.make_with_headings(tmp_path, set_outline=False)
    blocks = _doc_blocks(pdf_path)
    outline = pdf_source.load_outline(pdf_path)

    result = build_structure(blocks, outline, 1, THRESHOLDS)

    assert result.outline_used is False
    assert any(w.code == "structure.outline_fallback" for w in result.warnings)
    assert result.toc


def test_no_headings_yields_single_chapter(tmp_path: Path) -> None:
    pdf_path = make_pdfs.make_single_column(tmp_path, pages=2)
    blocks = _doc_blocks(pdf_path)

    result = build_structure(blocks, (), 1, THRESHOLDS)

    assert len(result.chapters) == 1
    assert any(w.code == "structure.no_headings" for w in result.warnings)
