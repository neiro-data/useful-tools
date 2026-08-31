"""Tests for pipeline.py."""

from html_to_epub.pipeline import _derive_author_from_url


def test_derive_author_from_url_strips_www_and_tld() -> None:
    assert _derive_author_from_url("https://www.tigerdata.com/some-url/more1") == "Tigerdata"


def test_derive_author_from_url_uses_registrable_label_under_subdomain() -> None:
    assert (
        _derive_author_from_url("https://docs.tigerdata.com/about/latest/changelog/") == "Tigerdata"
    )


def test_derive_author_from_url_single_label_host() -> None:
    assert _derive_author_from_url("http://localhost:8000/page") == "Localhost"


def test_derive_author_from_url_rejects_bare_ip() -> None:
    assert _derive_author_from_url("http://127.0.0.1/page") is None
