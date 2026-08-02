"""Tests for structure.py."""

from html_to_epub.structure import InputDoc, build_from_directory, build_from_single_document

FRAGMENT = (
    "<p>Leading text before any heading.</p>"
    '<h1 id="ch1">Chapter One</h1>'
    "<p>Chapter one body.</p>"
    '<h2 id="s1">Section One</h2>'
    "<p>Section text.</p>"
    "<h1>Chapter Two</h1>"
    "<p>Chapter two body.</p>"
)


def test_split_level_1_creates_leading_and_two_chapters() -> None:
    result = build_from_single_document(FRAGMENT, split_level=1)
    assert [c.title for c in result.chapters] == ["Untitled", "Chapter One", "Chapter Two"]
    assert result.chapters[0].file_name == "chap_0001.xhtml"
    assert "Leading text" in result.chapters[0].body_xhtml


def test_split_level_2_splits_on_h2_too() -> None:
    result = build_from_single_document(FRAGMENT, split_level=2)
    titles = [c.title for c in result.chapters]
    assert "Section One" in titles
    assert titles.count("Chapter One") == 1


def test_toc_nests_subheadings_under_chapter() -> None:
    result = build_from_single_document(FRAGMENT, split_level=1)
    top_titles = [n.title for n in result.toc]
    assert "Chapter One" in top_titles
    ch1 = next(n for n in result.toc if n.title == "Chapter One")
    assert any(c.title == "Section One" for c in ch1.children)


def test_anchor_href_rewritten_to_owning_chapter() -> None:
    fragment = (
        '<h1 id="a">A</h1><p><a href="#b">jump</a></p>'
        '<h1 id="c">C</h1><p><a id="b" href="#a">back</a></p>'
    )
    result = build_from_single_document(fragment, split_level=1)
    chap_a = next(c for c in result.chapters if c.title == "A")
    assert 'href="chap_0002.xhtml#b"' in chap_a.body_xhtml


def test_unresolvable_href_recorded_as_finding() -> None:
    fragment = '<h1 id="a">A</h1><p><a href="#nowhere">broken</a></p>'
    result = build_from_single_document(fragment, split_level=1)
    assert "#nowhere" in result.unresolved_hrefs


def test_spine_matches_chapter_order() -> None:
    result = build_from_single_document(FRAGMENT, split_level=1)
    file_names = [c.file_name for c in result.chapters]
    assert file_names == sorted(file_names)


def test_duplicate_id_across_files_resolves_to_owning_chapter() -> None:
    docs = [
        InputDoc(
            stem="01-first",
            xhtml_fragment='<h1 id="dup">First</h1><p><a href="#dup">link</a></p>',
            title="First",
        ),
        InputDoc(stem="02-second", xhtml_fragment='<h1 id="dup">Second</h1>', title="Second"),
    ]
    result = build_from_directory(docs, split_level=1)
    chap_first = next(c for c in result.chapters if c.title == "First")
    assert 'href="chap_0001.xhtml#dup"' in chap_first.body_xhtml


def test_directory_mode_one_chapter_per_file() -> None:
    docs = [
        InputDoc(stem="01-intro", xhtml_fragment='<h1 id="i">Intro</h1><p>Hi</p>', title="Intro"),
        InputDoc(
            stem="02-body",
            xhtml_fragment='<h1 id="b">Body</h1><p>Main</p><h2 id="d">Detail</h2><p>More</p>',
            title="Body",
        ),
    ]
    result = build_from_directory(docs, split_level=1)
    assert len(result.chapters) == 2
    assert result.chapters[0].file_name == "chap_0001.xhtml"
    body_toc = next(n for n in result.toc if n.title == "Body")
    assert any(c.title == "Detail" for c in body_toc.children)
