"""Orchestrate load -> normalize -> structure -> BookModel."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path

from html_to_epub.config import BuildConfig
from html_to_epub.extract import ExtractedArticle, extract_article
from html_to_epub.fetch import fetch_url
from html_to_epub.loaders import (
    RawDocument,
    load_documents,
    load_metadata_sidecar,
    scrape_author,
    scrape_title,
)
from html_to_epub.models import BookModel, Metadata
from html_to_epub.normalize import normalize_html
from html_to_epub.structure import (
    InputDoc,
    StructureResult,
    build_from_directory,
    build_from_single_document,
)

_MODIFIED_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def build_book_model(config: BuildConfig) -> tuple[BookModel, tuple[str, ...], tuple[str, ...]]:
    """Run the full pipeline and return (BookModel, unresolved_hrefs, fallback_warnings)."""
    overrides = load_metadata_sidecar(Path(config.metadata_path) if config.metadata_path else None)

    if config.urls:
        docs, is_dir, articles, raw_pages = _load_from_urls(config)
    else:
        if config.input_path is None:
            raise ValueError("either input_path or urls must be provided")
        input_path = Path(config.input_path)
        is_dir = input_path.is_dir()
        docs = load_documents(input_path)
        articles = [None] * len(docs)
        raw_pages = [d.raw_html for d in docs]

    normalized = [(d.file_stem, normalize_html(d.raw_html), d.raw_html) for d in docs]

    if is_dir:
        input_docs = [
            InputDoc(stem=stem, xhtml_fragment=frag, title=scrape_title(raw) or stem)
            for stem, frag, raw in normalized
        ]
        result: StructureResult = build_from_directory(input_docs, config.split_level)
    else:
        _, frag, _ = normalized[0]
        result = build_from_single_document(frag, config.split_level)

    fallback_stem = docs[0].file_stem
    scraped_title = scrape_title(raw_pages[0])
    scraped_author = scrape_author(raw_pages[0])
    primary_article = articles[0]
    extracted_title = primary_article.title if primary_article else None
    extracted_author = primary_article.author if primary_article else None
    extracted_date = primary_article.date if primary_article else None
    canonical_url = primary_article.canonical_url if primary_article else None

    title = config.title or overrides.title or extracted_title or scraped_title or fallback_stem
    author = config.author or overrides.author or extracted_author or scraped_author
    language = config.language or overrides.language or "en"
    identifier = (
        config.identifier or overrides.identifier or canonical_url or _content_hash(normalized)
    )
    # EPUB 3 requires dcterms:modified to be a CCYY-MM-DDThh:mm:ssZ timestamp; without a
    # sidecar override there is no meaningful "modified" time, so use a fixed epoch constant
    # rather than datetime.now() (non-deterministic) or a content hash (not a timestamp).
    modified = overrides.date or _valid_modified(extracted_date) or "1970-01-01T00:00:00Z"

    metadata = Metadata(
        identifier=identifier,
        title=title,
        language=language,
        author=author,
        publisher=None,
        modified=modified,
    )

    book = BookModel(
        metadata=metadata,
        chapters=result.chapters,
        toc=result.toc,
        spine=tuple(c.file_name for c in result.chapters),
    )
    fallback_warnings = tuple(
        f"trafilatura found no main content for {url}; used <body> fallback"
        for url, article in zip(config.urls, articles, strict=False)
        if article is not None and article.used_fallback
    )
    return book, result.unresolved_hrefs, fallback_warnings


def _content_hash(normalized: list[tuple[str, str, str]], prefix: str = "") -> str:
    hasher = hashlib.blake2b(digest_size=16)
    for stem, frag, _raw in normalized:
        hasher.update(stem.encode("utf-8"))
        hasher.update(frag.encode("utf-8"))
    return f"{prefix}{hasher.hexdigest()}"


def _load_from_urls(
    config: BuildConfig,
) -> tuple[list[RawDocument], bool, list[ExtractedArticle | None], list[str]]:
    """Fetch+extract each configured URL, returning docs in the same shape load_documents uses."""
    docs: list[RawDocument] = []
    articles: list[ExtractedArticle | None] = []
    raw_pages: list[str] = []
    for url in config.urls:
        page = fetch_url(url, timeout=config.timeout, user_agent=config.user_agent)
        article = extract_article(page.html, page.final_url)
        stem = article.title or slugify_url(page.final_url)
        docs.append(RawDocument(file_stem=stem, raw_html=article.html_fragment))
        articles.append(article)
        raw_pages.append(page.html)
    is_dir = len(docs) > 1
    return docs, is_dir, articles, raw_pages


def _valid_modified(date: str | None) -> str | None:
    """Return `date` only if it is a real, calendar-valid EPUB 3 dcterms:modified timestamp."""
    if not date:
        return None
    try:
        datetime.strptime(date, _MODIFIED_FORMAT)  # noqa: DTZ007 - format has no offset to parse
    except ValueError:
        return None
    return date


def slugify_url(url: str) -> str:
    """Derive a filesystem-safe stem from a URL for use as a chapter/file name."""
    slug = re.sub(r"^https?://", "", url)
    slug = re.sub(r"[^A-Za-z0-9]+", "-", slug).strip("-").lower()
    return slug or "page"
