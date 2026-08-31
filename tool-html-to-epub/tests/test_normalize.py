"""Tests for normalize.py."""

from xml.etree import ElementTree as ET

from html_to_epub.normalize import normalize_html


def test_drops_script_and_style_tags() -> None:
    html = "<body><p>Keep</p><script>alert(1)</script><style>.a{}</style></body>"
    result = normalize_html(html)
    assert "script" not in result
    assert "style" not in result
    assert "Keep" in result


def test_drops_img_and_media_tags() -> None:
    html = '<body><p>Text</p><img src="x.png"><video src="y.mp4"></video></body>'
    result = normalize_html(html)
    assert "<img" not in result
    assert "<video" not in result


def test_strips_event_and_style_attributes() -> None:
    html = '<body><p onclick="evil()" style="color:red">Text</p></body>'
    result = normalize_html(html)
    assert "onclick" not in result
    assert "style=" not in result


def test_unwraps_unknown_tags_but_keeps_text() -> None:
    html = "<body><div><span>Unwrapped text</span></div></body>"
    result = normalize_html(html)
    assert "<div" not in result
    assert "<span" not in result
    assert "Unwrapped text" in result


def test_keeps_allowed_tags() -> None:
    html = "<body><h1>Title</h1><p>Para</p><ul><li>Item</li></ul></body>"
    result = normalize_html(html)
    assert "<h1>" in result
    assert "<p>" in result
    assert "<li>" in result


def test_output_always_parses_as_xml() -> None:
    html = "<body><p>Unclosed<br>text</p><hr></body>"
    result = normalize_html(html)
    ET.fromstring(f"<root>{result}</root>")  # noqa: S314 - trusted, self-produced XHTML


def test_void_elements_self_closed() -> None:
    html = "<body><p>a</p><hr><p>b</p></body>"
    result = normalize_html(html)
    assert "<hr/>" in result


def test_html_comments_are_dropped_not_rendered() -> None:
    html = "<body><p>Hello<!-- internal note --> World</p></body>"
    result = normalize_html(html)
    assert "internal note" not in result
    assert "Hello" in result
    assert "World" in result
