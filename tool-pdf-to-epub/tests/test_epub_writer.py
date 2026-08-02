"""Tests for epub_writer.py: valid output and byte-for-byte determinism."""

from __future__ import annotations

import filecmp
import time
from pathlib import Path

from pdf_to_epub.epub_writer import write_epub
from pdf_to_epub.models import BookModel, Chapter, Metadata, TocNode, Warning
from pdf_to_epub.validator import validate_epub_file

_METADATA = Metadata(
    identifier="urn:uuid:test",
    title="Test Book",
    language="en",
    author="An Author",
    publisher="A Publisher",
    modified="2000-01-01T00:00:00Z",
)


def _book() -> BookModel:
    chapter1 = Chapter(
        id="c1",
        title="Chapter One",
        file_name="c1.xhtml",
        body_xhtml="<p>Hello</p>",
        anchors=("intro",),
    )
    chapter2 = Chapter(
        id="c2",
        title="Chapter Two",
        file_name="c2.xhtml",
        body_xhtml="<p>World</p>",
        anchors=(),
    )
    toc = (
        TocNode(
            title="Chapter One",
            href="c1.xhtml#intro",
            children=(TocNode(title="Chapter Two", href="c2.xhtml", children=()),),
        ),
    )
    warning = Warning(code="ok", message="none", page=None, severity="warning")
    return BookModel(
        metadata=_METADATA,
        chapters=(chapter1, chapter2),
        toc=toc,
        spine=("c1.xhtml", "c2.xhtml"),
        warnings=(warning,),
    )


def test_write_epub_produces_valid_file(tmp_path: Path) -> None:
    output_path = tmp_path / "book.epub"
    write_epub(_book(), output_path)
    findings = validate_epub_file(output_path)
    assert not any(f.level == "error" for f in findings)


def test_write_epub_is_deterministic(tmp_path: Path) -> None:
    book = _book()
    output_a = tmp_path / "a.epub"
    output_b = tmp_path / "b.epub"

    write_epub(book, output_a)
    time.sleep(1.1)
    write_epub(book, output_b)

    assert filecmp.cmp(output_a, output_b, shallow=False)
