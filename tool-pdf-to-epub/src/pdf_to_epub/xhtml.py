"""XHTML markup helpers. Stdlib only; no third-party imports."""

from __future__ import annotations

from xml.etree import ElementTree as ET


def escape_text(text: str) -> str:
    """Escape the three characters that are unsafe in XML text content."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


STYLESHEET_HREF = "style/stylesheet.css"

STYLESHEET_CSS = """\
body {
  font-family: Georgia, "Times New Roman", serif;
  line-height: 1.5;
  margin: 0 5%;
  text-align: justify;
}
p {
  margin: 0 0 0.6em;
  text-indent: 0;
}
h1, h2, h3 {
  font-weight: bold;
  line-height: 1.25;
  text-align: left;
  page-break-after: avoid;
}
h1 {
  font-size: 1.6em;
  margin-top: 1.4em;
}
h2 {
  font-size: 1.3em;
  margin-top: 1.2em;
}
h3 {
  font-size: 1.1em;
  margin-top: 1em;
}
p.caption {
  font-size: 0.9em;
  font-style: italic;
  text-align: center;
  margin: 1.2em 5% 1.4em;
  color: #444;
}
table {
  border-collapse: collapse;
}
th, td {
  border: 1px solid #999;
  padding: 0.3em 0.5em;
}
"""


def paragraph(text: str, css_class: str | None = None) -> str:
    """Wrap already-escaped-or-plain text in a ``<p>`` element, escaping it first."""
    if css_class is not None:
        return f'<p class="{escape_text(css_class)}">{escape_text(text)}</p>'
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
        f"<head><title>{escape_text(title)}</title>"
        # Note: ebooklib's EpubHtml.get_content() rebuilds <head> from self.links and
        # discards this tag in the shipped EPUB — epub_writer.py's add_link() call is the
        # mechanism that actually links the stylesheet. Kept here for direct consumers of
        # this raw XHTML string (tests, standalone rendering).
        f'<link rel="stylesheet" type="text/css" href="{STYLESHEET_HREF}"/></head>\n'
        f"<body>{body_fragment}</body>\n"
        "</html>"
    )
