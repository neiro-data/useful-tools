from __future__ import annotations

import io
import urllib.error

import pytest
from PIL import Image

from config_gui import icons


def _ico_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGBA", (32, 32), (200, 30, 30, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_fetch_caches_the_icon_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_download(domain: str) -> bytes:
        calls.append(domain)
        return _ico_bytes()

    monkeypatch.setattr(icons, "_download", fake_download)
    first = icons.fetch("example.com")
    second = icons.fetch("example.com")

    assert first == second == icons.icon_path("example.com")
    assert calls == ["example.com"], "a cached icon must not be re-fetched"
    with Image.open(first) as image:
        assert image.size == (icons.ICON_SIZE, icons.ICON_SIZE)


@pytest.mark.parametrize(
    "failure",
    [
        urllib.error.URLError("offline"),
        TimeoutError(),
        OSError("refused"),
    ],
)
def test_fetch_falls_back_to_the_globe(monkeypatch: pytest.MonkeyPatch, failure: Exception) -> None:
    def fake_download(domain: str) -> bytes:
        raise failure

    monkeypatch.setattr(icons, "_download", fake_download)
    assert icons.fetch("example.com") == icons.globe_path()
    assert icons.globe_path().exists()


def test_fetch_falls_back_when_the_body_is_not_an_image(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(icons, "_download", lambda domain: b"<html>404</html>")
    assert icons.fetch("example.com") == icons.globe_path()


def test_fetch_falls_back_when_the_body_is_oversized(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(icons, "_download", lambda domain: b"x" * (icons.MAX_ICON_BYTES + 1))
    assert icons.fetch("example.com") == icons.globe_path()


def test_no_domain_gets_the_globe() -> None:
    assert icons.fetch("") == icons.globe_path()
