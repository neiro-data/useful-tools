"""Sanitize raw HTML into a well-formed XHTML body fragment.

Uses BeautifulSoup with the lxml parser. Disallowed elements are dropped
entirely (their content is meaningless/unsafe: script, style, media embeds);
unknown/other disallowed elements are unwrapped so their text survives.
"""

from __future__ import annotations

from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup
from bs4.element import NavigableString, PreformattedString, Tag

DROP_TAGS = {"script", "style", "img", "picture", "video", "iframe"}

KEEP_TAGS = {
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "p",
    "ul",
    "ol",
    "li",
    "blockquote",
    "pre",
    "code",
    "a",
    "em",
    "strong",
    "hr",
    "table",
    "thead",
    "tbody",
    "tr",
    "td",
    "th",
    "body",
    "br",
}

VOID_TAGS = {"hr", "br"}


def normalize_html(raw_html: str) -> str:
    """Parse raw HTML and return a well-formed XHTML body-fragment string.

    Guarantees: no script/style/on*/style-attr survive, only KEEP_TAGS
    remain, void elements are self-closed, and the result always parses
    with xml.etree.ElementTree (wrapped in a synthetic root).
    """
    soup = BeautifulSoup(raw_html, "lxml")
    body = soup.body or soup

    for tag in body.find_all(list(DROP_TAGS)):
        tag.decompose()

    for tag in body.find_all(True):
        if not isinstance(tag, Tag):
            continue
        _strip_unsafe_attrs(tag)
        if tag.name not in KEEP_TAGS:
            tag.unwrap()

    fragment = "".join(str(child) for child in body.contents) if body else ""
    xhtml = _to_xhtml(fragment)
    _assert_parseable(xhtml)
    return xhtml


def _strip_unsafe_attrs(tag: Tag) -> None:
    for attr in list(tag.attrs):
        if attr.lower().startswith("on") or attr.lower() == "style":
            del tag.attrs[attr]


def _to_xhtml(fragment: str) -> str:
    """Re-parse the fragment and emit self-closed void elements + numeric entities."""
    soup = BeautifulSoup(fragment, "lxml")
    body = soup.body or soup
    parts: list[str] = []
    for child in body.contents:
        parts.append(_render_node(child))
    return "".join(parts)


def render_node(node: object) -> str:
    """Render a bs4 node (Tag or NavigableString) back into XHTML. Public for reuse."""
    if isinstance(node, PreformattedString):
        return ""
    if isinstance(node, NavigableString):
        return _escape_text(str(node))
    if isinstance(node, Tag):
        return _render_tag(node)
    return ""


_render_node = render_node


def _render_tag(tag: Tag) -> str:
    attrs = "".join(f' {k}="{_escape_attr(str(v))}"' for k, v in tag.attrs.items())
    if tag.name in VOID_TAGS:
        return f"<{tag.name}{attrs}/>"
    inner = "".join(render_node(child) for child in tag.contents)
    return f"<{tag.name}{attrs}>{inner}</{tag.name}>"


def _escape_text(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _escape_attr(text: str) -> str:
    return _escape_text(text).replace('"', "&quot;")


def _assert_parseable(xhtml: str) -> None:
    wrapped = f"<root>{xhtml}</root>"
    try:
        ET.fromstring(wrapped)  # noqa: S314 - trusted, self-produced XHTML
    except ET.ParseError as exc:
        raise ValueError(f"normalize_html produced unparseable XHTML: {exc}") from exc
