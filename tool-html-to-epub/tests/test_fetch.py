"""Tests for html_to_epub.fetch. No network access — httpx transport is mocked."""

from __future__ import annotations

import httpx
import pytest

from html_to_epub.fetch import MAX_BODY_BYTES, fetch_url

_RealClient = httpx.Client


def test_rejects_file_scheme() -> None:
    with pytest.raises(ValueError, match="unsupported URL scheme"):
        fetch_url("file:///etc/passwd")


def test_rejects_ftp_scheme() -> None:
    with pytest.raises(ValueError, match="unsupported URL scheme"):
        fetch_url("ftp://example.com/file.html")


def test_non_2xx_status_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    transport = httpx.MockTransport(handler)

    def fake_client(*args: object, **kwargs: object) -> httpx.Client:
        return _RealClient(transport=transport)

    monkeypatch.setattr(httpx, "Client", fake_client)
    with pytest.raises(ValueError, match="status 404"):
        fetch_url("https://example.com/missing")


def test_oversize_body_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    big_body = b"x" * (MAX_BODY_BYTES + 1)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=big_body)

    transport = httpx.MockTransport(handler)

    def fake_client(*args: object, **kwargs: object) -> httpx.Client:
        return _RealClient(transport=transport)

    monkeypatch.setattr(httpx, "Client", fake_client)
    with pytest.raises(ValueError, match="exceeds"):
        fetch_url("https://example.com/huge")


def test_redirect_to_disallowed_scheme_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, html="<html><body><p>hi</p></body></html>")

    transport = httpx.MockTransport(handler)

    def fake_client(*args: object, **kwargs: object) -> httpx.Client:
        client = _RealClient(transport=transport)
        # Simulate a response whose final URL escaped to a disallowed scheme, independent
        # of how httpx itself would actually behave on a cross-scheme redirect.
        monkeypatch.setattr(httpx.Response, "url", httpx.URL("ftp://example.com/evil"))
        return client

    monkeypatch.setattr(httpx, "Client", fake_client)
    with pytest.raises(ValueError, match="redirect escaped to unsupported scheme"):
        fetch_url("https://example.com/page")


def test_successful_fetch_returns_page(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, html="<html><body><p>hi</p></body></html>")

    transport = httpx.MockTransport(handler)

    def fake_client(*args: object, **kwargs: object) -> httpx.Client:
        return _RealClient(transport=transport)

    monkeypatch.setattr(httpx, "Client", fake_client)
    page = fetch_url("https://example.com/page")
    assert page.url == "https://example.com/page"
    assert "hi" in page.html
