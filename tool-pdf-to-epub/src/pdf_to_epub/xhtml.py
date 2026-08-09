"""XHTML markup helpers. Stdlib only; no third-party imports."""

from __future__ import annotations

from xml.etree import ElementTree as ET


def escape_text(text: str) -> str:
    """Escape the three characters that are unsafe in XML text content."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def paragraph(text: str) -> str:
    """Wrap already-escaped-or-plain text in a ``<p>`` element, escaping it first."""
    return f"<p>{escape_text(text)}</p>"


def heading(level: int, text: str, anchor: str) -> str:
    """Build an ``<hN>`` element carrying an ``id`` anchor for TOC linking."""
    return f'<h{level} id="{escape_text(anchor)}">{escape_text(text)}</h{level}>'


def assert_parseable(fragment: str) -> None:
    """Raise ValueError if ``fragment`` does not parse as XML under a synthetic root."""
    wrapped = f"<root>{fragment}</root>"
    try:
        ET.fromstring(wrapped)  # noqa: S314 - internally produced XHTML
    except ET.ParseError as exc:
        raise ValueError(f"fragment is not parseable XHTML: {exc}") from exc


def wrap_document(title: str, body_fragment: str) -> str:
    """Wrap a body fragment into a full XHTML 1.1 / EPUB 3 document string."""
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml">\n'
        f"<head><title>{escape_text(title)}</title></head>\n"
        f"<body>{body_fragment}</body>\n"
        "</html>"
    )
