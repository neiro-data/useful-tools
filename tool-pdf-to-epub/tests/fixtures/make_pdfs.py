"""Programmatic PDF fixture builder using PyMuPDF. Test tooling only."""

from __future__ import annotations

from pathlib import Path

import fitz

PAGE_WIDTH = 612.0
PAGE_HEIGHT = 792.0
FONT_SIZE = 11.0

_LEFT_SENTENCES = [
    "The quiet valley stretched beneath a low autumn sky.",
    "Farmers gathered the last of the wheat before the rains came.",
    "A single road wound through the hills toward the distant town.",
    "Children played near the old stone bridge until dusk settled in.",
    "Smoke rose steadily from every chimney along the narrow street.",
    "Nobody could recall a harvest quite so generous as this one.",
    "The miller's wheel turned slowly against the current all night.",
    "Travelers spoke of the valley long after they had left it behind.",
]

_RIGHT_SENTENCES = [
    "Far to the east the mountains held their snow well into summer.",
    "Traders crossed the pass carrying salt, wool, and rare spices.",
    "The old watchtower had stood empty for nearly a hundred years.",
    "Stories about the tower kept the village children close to home.",
    "Every spring the river swelled and carved a new path downhill.",
    "Fishermen learned to read the water before they read anything else.",
    "The harbor bustled with boats returning before the storm arrived.",
    "By nightfall the entire coast smelled faintly of salt and rain.",
]


def _paragraph(sentences: list[int]) -> str:
    return " ".join(_LEFT_SENTENCES[i % len(_LEFT_SENTENCES)] for i in sentences)


def make_single_column(directory: Path, pages: int = 3) -> Path:
    """Build a single-column, born-digital PDF with several pages of real sentences."""
    doc = fitz.open()
    for _p in range(pages):
        page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        rect = fitz.Rect(72, 72, PAGE_WIDTH - 72, PAGE_HEIGHT - 72)
        text = " ".join(_LEFT_SENTENCES * 6)
        page.insert_textbox(rect, text, fontsize=FONT_SIZE, fontname="helv")
    path = directory / "single_column.pdf"
    doc.save(path)
    doc.close()
    return path


def make_two_column(directory: Path, pages: int = 1) -> Path:
    """Build a two-column PDF: left column fully, then right column, per page."""
    doc = fitz.open()
    left_text = " ".join(_LEFT_SENTENCES * 3)
    right_text = " ".join(_RIGHT_SENTENCES * 3)
    for _p in range(pages):
        page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        left_rect = fitz.Rect(72, 100, 288, PAGE_HEIGHT - 72)
        right_rect = fitz.Rect(324, 100, 540, PAGE_HEIGHT - 72)
        page.insert_textbox(left_rect, left_text, fontsize=FONT_SIZE, fontname="helv")
        page.insert_textbox(right_rect, right_text, fontsize=FONT_SIZE, fontname="helv")
    path = directory / "two_column.pdf"
    doc.save(path)
    doc.close()
    return path


def make_two_column_with_bands(directory: Path) -> Path:
    """Build a two-column page with a full-width title band and a full-width caption band."""
    doc = fitz.open()
    page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)

    title_rect = fitz.Rect(72, 60, PAGE_WIDTH - 72, 96)
    page.insert_textbox(
        title_rect,
        "The Complete History of the Valley",
        fontsize=16,
        fontname="helv",
        align=fitz.TEXT_ALIGN_CENTER,
    )

    left_text = " ".join(_LEFT_SENTENCES * 2)
    right_text = " ".join(_RIGHT_SENTENCES * 2)
    left_rect = fitz.Rect(72, 110, 288, 620)
    right_rect = fitz.Rect(324, 110, 540, 620)
    page.insert_textbox(left_rect, left_text, fontsize=FONT_SIZE, fontname="helv")
    page.insert_textbox(right_rect, right_text, fontsize=FONT_SIZE, fontname="helv")

    caption_rect = fitz.Rect(72, 630, PAGE_WIDTH - 72, 650)
    page.insert_textbox(
        caption_rect,
        "Figure 1: A detailed map of the valley and its surrounding hills and rivers.",
        fontsize=9,
        fontname="helv",
        align=fitz.TEXT_ALIGN_CENTER,
    )

    path = directory / "two_column_bands.pdf"
    doc.save(path)
    doc.close()
    return path


def add_running_head(src: Path, dest: Path, header: str = "The Valley Chronicles") -> Path:
    """Copy a PDF and stamp a running header and page number onto every page."""
    doc = fitz.open(src)
    for index in range(doc.page_count):
        page = doc[index]
        page.insert_text((72, 40), header, fontsize=9, fontname="helv")
        page.insert_text(
            (PAGE_WIDTH / 2 - 5, PAGE_HEIGHT - 30),
            str(index + 1),
            fontsize=9,
            fontname="helv",
        )
    doc.save(dest)
    doc.close()
    return dest


def make_table_page(directory: Path) -> Path:
    """Build a page containing a simple bordered table."""
    doc = fitz.open()
    page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)

    rows = [
        ["Name", "Age", "City"],
        ["Alice", "30", "Boston"],
        ["Bob", "25", "Chicago"],
        ["Carol", "35", "Denver"],
    ]
    x0, y0 = 72, 100
    col_w, row_h = 120, 24
    n_cols, n_rows = len(rows[0]), len(rows)

    for r in range(n_rows + 1):
        y = y0 + r * row_h
        page.draw_line((x0, y), (x0 + n_cols * col_w, y))
    for c in range(n_cols + 1):
        x = x0 + c * col_w
        page.draw_line((x, y0), (x, y0 + n_rows * row_h))

    for r, row in enumerate(rows):
        for c, cell in enumerate(row):
            px = x0 + c * col_w + 5
            py = y0 + r * row_h + 16
            page.insert_text((px, py), cell, fontsize=10, fontname="helv")

    body_rect = fitz.Rect(x0, y0 + (n_rows + 1) * row_h + 20, PAGE_WIDTH - 72, PAGE_HEIGHT - 72)
    page.insert_textbox(
        body_rect, " ".join(_LEFT_SENTENCES * 4), fontsize=FONT_SIZE, fontname="helv"
    )

    path = directory / "table_page.pdf"
    doc.save(path)
    doc.close()
    return path


def make_ragged_table_page(directory: Path) -> Path:
    """Build a page with a table that has an inconsistent column count per row."""
    doc = fitz.open()
    page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    page.insert_text((72, 120), "Name  Age  City", fontsize=10, fontname="helv")
    page.insert_text((72, 140), "Alice  30", fontsize=10, fontname="helv")
    page.insert_text((72, 160), "Bob  25  Chicago  Extra", fontsize=10, fontname="helv")
    path = directory / "ragged_table_page.pdf"
    doc.save(path)
    doc.close()
    return path


def make_with_headings(directory: Path, *, set_outline: bool = False) -> Path:
    """Build a multi-chapter, single-column PDF with h1/h2/h3-sized headings."""
    doc = fitz.open()
    toc: list[list[object]] = []
    chapters = [
        ("Chapter One: The Valley", "Introduction", _LEFT_SENTENCES[:4]),
        ("Chapter Two: The Mountains", "Background", _RIGHT_SENTENCES[:4]),
    ]
    for chap_title, sub_title, sentences in chapters:
        page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        y = 100
        page.insert_text((72, y), chap_title, fontsize=24, fontname="helv")
        toc.append([1, chap_title, page.number + 1])
        y += 40
        page.insert_text((72, y), sub_title, fontsize=16, fontname="helv")
        toc.append([2, sub_title, page.number + 1])
        y += 30
        rect = fitz.Rect(72, y, PAGE_WIDTH - 72, PAGE_HEIGHT - 72)
        page.insert_textbox(rect, " ".join(sentences), fontsize=FONT_SIZE, fontname="helv")
    if set_outline:
        doc.set_toc(toc)
    path = directory / ("with_headings_outline.pdf" if set_outline else "with_headings.pdf")
    doc.save(path)
    doc.close()
    return path


def make_messy(directory: Path) -> Path:
    """Build a mostly-clean PDF with one near-empty page, dragging its confidence down."""
    doc = fitz.open()
    page1 = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    rect = fitz.Rect(72, 72, PAGE_WIDTH - 72, PAGE_HEIGHT - 72)
    page1.insert_textbox(rect, " ".join(_LEFT_SENTENCES * 6), fontsize=FONT_SIZE, fontname="helv")
    page2 = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    page2.insert_text((72, 100), "x", fontsize=6, fontname="helv")
    path = directory / "messy.pdf"
    doc.save(path)
    doc.close()
    return path


def make_scanned(directory: Path) -> Path:
    """Build an image-only page with no extractable text layer."""
    src_doc = fitz.open()
    src_page = src_doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    src_page.insert_textbox(
        fitz.Rect(72, 72, 540, 720), "Scanned page content rendered as an image.", fontsize=14
    )
    pix = src_page.get_pixmap()
    src_doc.close()

    doc = fitz.open()
    page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    page.insert_image(fitz.Rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT), pixmap=pix)
    path = directory / "scanned.pdf"
    doc.save(path)
    doc.close()
    return path
