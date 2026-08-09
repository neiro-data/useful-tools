"""Tests for models.py construction, validator.py checks, and xhtml.py helpers."""

from __future__ import annotations

import pytest

from pdf_to_epub.models import BookModel, Chapter, Metadata, TocNode, Warning
from pdf_to_epub.validator import validate_model
from pdf_to_epub.xhtml import assert_parseable, escape_text

_METADATA = Metadata(
    identifier="urn:uuid:test",
    title="Test Book",
    language="en",
    author="An Author",
    publisher="A Publisher",
    modified="2000-01-01T00:00:00Z",
)


def _valid_book() -> BookModel:
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
            children=(TocNode(title="Sub", href="c2.xhtml", children=()),),
        ),
    )
    warning = Warning(
        code="low-confidence-table", message="dropped a table", page=3, severity="warning"
    )
    return BookModel(
        metadata=_METADATA,
        chapters=(chapter1, chapter2),
        toc=toc,
        spine=("c1.xhtml", "c2.xhtml"),
        warnings=(warning,),
    )


def test_valid_book_has_no_error_findings() -> None:
    findings = validate_model(_valid_book())
    assert not any(f.level == "error" for f in findings)


def test_valid_book_surfaces_warning_as_finding() -> None:
    findings = validate_model(_valid_book())
    assert any(f.level == "warning" and "dropped a table" in f.message for f in findings)


def test_validate_model_flags_unknown_spine_entry() -> None:
    book = _valid_book()
    bad_book = BookModel(
        metadata=book.metadata,
        chapters=book.chapters,
        toc=book.toc,
        spine=(*book.spine, "missing.xhtml"),
    )
    findings = validate_model(bad_book)
    assert any("missing.xhtml" in f.message for f in findings)


def test_validate_model_flags_empty_chapter_body() -> None:
    book = _valid_book()
    empty_chapter = Chapter(
        id="c3", title="Empty", file_name="c3.xhtml", body_xhtml="  ", anchors=()
    )
    bad_book = BookModel(
        metadata=book.metadata,
        chapters=(*book.chapters, empty_chapter),
        toc=book.toc,
        spine=(*book.spine, "c3.xhtml"),
    )
    findings = validate_model(bad_book)
    assert any("empty body" in f.message for f in findings)


def test_validate_model_flags_unknown_toc_href() -> None:
    book = _valid_book()
    bad_toc = (*book.toc, TocNode(title="Ghost", href="ghost.xhtml", children=()))
    bad_book = BookModel(
        metadata=book.metadata,
        chapters=book.chapters,
        toc=bad_toc,
        spine=book.spine,
    )
    findings = validate_model(bad_book)
    assert any("ghost.xhtml" in f.message for f in findings)


def test_escape_text_escapes_ampersand_lt_gt() -> None:
    assert escape_text("A & B < C > D") == "A &amp; B &lt; C &gt; D"


def test_assert_parseable_accepts_well_formed_fragment() -> None:
    assert_parseable("<p>hello <em>world</em></p>")


def test_assert_parseable_rejects_malformed_markup() -> None:
    with pytest.raises(ValueError, match="not parseable"):
        assert_parseable("<p>unclosed")
