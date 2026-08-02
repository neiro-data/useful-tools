"""Tests for validator.py."""

from html_to_epub.models import BookModel, Chapter, Metadata, TocNode
from html_to_epub.validator import validate_model

VALID_META = Metadata(
    identifier="id-1",
    title="Book",
    language="en",
    author=None,
    publisher=None,
    modified="hash123",
)
VALID_CHAPTER = Chapter(
    id="chap_0001",
    title="One",
    file_name="chap_0001.xhtml",
    body_xhtml="<p>Text</p>",
    anchors=("anchor1",),
)
VALID_TOC = (TocNode(title="One", href="chap_0001.xhtml", children=()),)


def _model(**overrides: object) -> BookModel:
    defaults: dict[str, object] = {
        "metadata": VALID_META,
        "chapters": (VALID_CHAPTER,),
        "toc": VALID_TOC,
        "spine": ("chap_0001.xhtml",),
    }
    defaults.update(overrides)
    return BookModel(**defaults)  # type: ignore[arg-type]


def test_valid_model_has_no_errors() -> None:
    findings = validate_model(_model())
    assert not [f for f in findings if f.level == "error"]


def test_empty_identifier_fails() -> None:
    bad_meta = Metadata(
        identifier="", title="Book", language="en", author=None, publisher=None, modified="h"
    )
    findings = validate_model(_model(metadata=bad_meta))
    assert any("identifier" in f.message for f in findings)


def test_empty_title_fails() -> None:
    bad_meta = Metadata(
        identifier="id", title="", language="en", author=None, publisher=None, modified="h"
    )
    findings = validate_model(_model(metadata=bad_meta))
    assert any("title" in f.message for f in findings)


def test_spine_referencing_unknown_chapter_fails() -> None:
    findings = validate_model(_model(spine=("chap_9999.xhtml",)))
    assert any("spine" in f.message for f in findings)


def test_empty_chapter_body_fails() -> None:
    empty_chapter = Chapter(
        id="chap_0001", title="One", file_name="chap_0001.xhtml", body_xhtml="   ", anchors=()
    )
    findings = validate_model(_model(chapters=(empty_chapter,)))
    assert any("empty body" in f.message for f in findings)


def test_toc_href_to_unknown_file_fails() -> None:
    bad_toc = (TocNode(title="Ghost", href="chap_9999.xhtml", children=()),)
    findings = validate_model(_model(toc=bad_toc))
    assert any("unknown file" in f.message for f in findings)


def test_toc_anchor_not_found_fails() -> None:
    bad_toc = (TocNode(title="One", href="chap_0001.xhtml#missing", children=()),)
    findings = validate_model(_model(toc=bad_toc))
    assert any("anchor not found" in f.message for f in findings)
