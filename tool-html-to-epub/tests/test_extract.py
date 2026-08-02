"""Tests for html_to_epub.extract."""

from __future__ import annotations

from pathlib import Path

from html_to_epub.extract import extract_article

FIXTURES = Path(__file__).parent / "fixtures"
BASE_URL = "https://example.com/blog/post"


def test_article_text_kept_and_boilerplate_dropped() -> None:
    html = (FIXTURES / "webpage.html").read_text(encoding="utf-8")
    article = extract_article(html, BASE_URL)

    assert "Deterministic builds are a foundational technique" in article.html_fragment
    for noise in ("Accept all cookies", "Related post one", "Copyright 2024", "Home", "About"):
        assert noise not in article.html_fragment


def test_relative_href_and_anchor_are_absolutized() -> None:
    html = (FIXTURES / "webpage.html").read_text(encoding="utf-8")
    article = extract_article(html, BASE_URL)

    assert 'href="https://example.com/relative/path"' in article.html_fragment
    assert 'href="https://example.com#section-2"' in article.html_fragment


def test_extracted_metadata() -> None:
    html = (FIXTURES / "webpage.html").read_text(encoding="utf-8")
    article = extract_article(html, BASE_URL)

    assert article.title == "Understanding Deterministic Builds"
    assert article.author == "Ada Example"
    assert article.canonical_url == BASE_URL


def test_fallback_to_body_when_trafilatura_finds_nothing() -> None:
    html = '<body><p>fallback content</p><a href="/relative">a link</a></body>'
    article = extract_article(html, BASE_URL)

    assert article.used_fallback is True
    assert "fallback content" in article.html_fragment
    assert 'href="https://example.com/relative"' in article.html_fragment


def test_used_fallback_false_when_trafilatura_succeeds() -> None:
    html = (FIXTURES / "webpage.html").read_text(encoding="utf-8")
    article = extract_article(html, BASE_URL)

    assert article.used_fallback is False


def test_extracted_date_is_pinned_not_resolved_against_now() -> None:
    """Guard against htmldate/dateparser resolving an unambiguous date against wall-clock time.

    That would make `modified` vary run to run and break the tool's byte-determinism guarantee.
    """
    html = (FIXTURES / "dated_article.html").read_text(encoding="utf-8")
    article = extract_article(html, "https://example.com/dated")

    assert article.date == "2019-03-14"
