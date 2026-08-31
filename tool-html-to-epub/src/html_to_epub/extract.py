"""Extract main-article content from a raw web page. Sole importer of trafilatura here."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin

import trafilatura
from bs4 import BeautifulSoup


@dataclass(frozen=True)
class ExtractedArticle:
    """The extracted article body plus whatever metadata trafilatura could find."""

    html_fragment: str
    title: str | None
    author: str | None
    date: str | None
    canonical_url: str | None
    used_fallback: bool = False
    """True when trafilatura found no main content and the whole <body> was used instead.

    This module stays free of CLI/printing concerns; callers surface this to the user.
    """


def extract_article(html: str, base_url: str) -> ExtractedArticle:
    """Pull the main content out of `html`, discarding nav/ads/footers/boilerplate.

    Falls back to the whole <body> when trafilatura finds nothing; see `used_fallback`.
    """
    fragment = trafilatura.extract(
        html,
        url=base_url,
        output_format="html",
        include_links=True,
        include_formatting=True,
        favor_precision=False,
    )
    metadata = trafilatura.extract_metadata(html, default_url=base_url)

    used_fallback = not fragment
    if fragment:
        body_html = _body_inner_html(fragment)
    else:
        body_html = _absolutize(_body_inner_html(html), base_url)

    title = metadata.title if metadata and metadata.title else None
    author = metadata.author if metadata and metadata.author else None
    date = metadata.date if metadata and metadata.date else None
    canonical_url = metadata.url if metadata and metadata.url else None

    return ExtractedArticle(
        html_fragment=body_html,
        title=title,
        author=author,
        date=date,
        canonical_url=canonical_url,
        used_fallback=used_fallback,
    )


def _body_inner_html(html: str) -> str:
    """Return the innerHTML of <body>, or the whole document if there is none."""
    soup = BeautifulSoup(html, "lxml")
    body = soup.body
    if body is None:
        return html
    return "".join(str(child) for child in body.contents)


def _absolutize(fragment_html: str, base_url: str) -> str:
    """Rewrite relative href targets against `base_url`."""
    soup = BeautifulSoup(fragment_html, "lxml")
    for tag in soup.find_all("a", href=True):
        href = tag["href"]
        if isinstance(href, str):
            tag["href"] = urljoin(base_url, href)
    body = soup.body
    if body is not None:
        return "".join(str(child) for child in body.contents)
    return str(soup)
