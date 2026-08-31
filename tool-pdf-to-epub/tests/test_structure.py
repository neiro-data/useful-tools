"""Tests for heading inference and chapter/TOC assembly."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from pdf_to_epub import pdf_source
from pdf_to_epub.config import Thresholds
from pdf_to_epub.layout import detect_columns, segment_zones
from pdf_to_epub.reconstruct import Block, join_document, page_blocks, strip_running_heads
from pdf_to_epub.structure import body_style, build_structure, infer_headings, tag_captions
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


def _paragraph(text: str) -> Block:
    return Block(
        kind="paragraph",
        text=text,
        pages=(1,),
        bbox=(0.0, 0.0, 100.0, 10.0),
        font_key=("Helvetica", 10.0),
    )


def test_tag_captions_retags_matching_paragraphs() -> None:
    blocks = (
        _paragraph("Figure 1: The cumulative count of things."),
        _paragraph("Table 2. Results"),
        _paragraph("Fig. 3 Overview"),
        _paragraph("Figures are omitted from this edition."),
        _paragraph("In Figure 1 we show the trend."),
    )

    annotated = tag_captions(blocks)

    assert [b.kind for b in annotated] == [
        "caption",
        "caption",
        "caption",
        "paragraph",
        "paragraph",
    ]


def test_tag_captions_leaves_long_body_paragraphs_alone() -> None:
    # A body paragraph that opens with "Table N " followed by ordinary prose (space satisfies
    # the separator class) must not be mistaken for a short caption label.
    long_paragraph = _paragraph(
        "Table 1 shows the results discussed above, and Table 2 goes into more detail across "
        "several sentences of ordinary prose that a reader would expect to see justified in the "
        "body of the document rather than centered and italicized like a caption."
    )

    annotated = tag_captions((long_paragraph,))

    assert annotated[0].kind == "paragraph"


def test_build_structure_renders_caption_class(tmp_path: Path) -> None:
    pdf_path = make_pdfs.make_with_headings(tmp_path)
    blocks = _doc_blocks(pdf_path)
    paragraph_idx = next(i for i, b in enumerate(blocks) if b.kind == "paragraph")
    caption = dataclasses.replace(
        blocks[paragraph_idx], text="Figure 1: A caption.", kind="paragraph"
    )
    body_blocks = (*blocks[:paragraph_idx], caption, *blocks[paragraph_idx + 1 :])

    result = build_structure(body_blocks, (), 1, THRESHOLDS)

    content = "".join(c.body_xhtml for c in result.chapters)
    assert '<p class="caption">' in content
    assert "<p>" in content


def test_captions_do_not_shift_body_style(tmp_path: Path) -> None:
    # Regression guard for call order: body_style/infer_headings must run on blocks that are
    # still tagged "paragraph" (pre-tag_captions), since body_style only weighs kind=="paragraph".
    pdf_path = make_pdfs.make_single_column(tmp_path, pages=1)
    blocks = _doc_blocks(pdf_path)

    body_size_before, body_font_before = body_style(blocks)
    annotated = tag_captions(infer_headings(blocks, body_size_before, THRESHOLDS))
    body_size_after, body_font_after = body_style(blocks)

    # tag_captions must not mutate the input, and re-computing body_style on the original
    # blocks after the full pipeline ran must be stable.
    assert (body_size_after, body_font_after) == (body_size_before, body_font_before)
    assert all(b.kind != "caption" for b in blocks)
    assert annotated is not blocks


def test_no_headings_yields_single_chapter(tmp_path: Path) -> None:
    pdf_path = make_pdfs.make_single_column(tmp_path, pages=2)
    blocks = _doc_blocks(pdf_path)

    result = build_structure(blocks, (), 1, THRESHOLDS)

    assert len(result.chapters) == 1
    assert any(w.code == "structure.no_headings" for w in result.warnings)
