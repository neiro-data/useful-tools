"""Orchestrate load -> normalize -> structure -> BookModel."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from html_to_epub.config import BuildConfig
from html_to_epub.extract import ExtractedArticle, extract_article
from html_to_epub.fetch import fetch_url
from html_to_epub.loaders import (
    MetadataOverrides,
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

    book = _resolve_metadata_and_build(
        config, overrides, docs, raw_pages, articles, normalized, result
    )
    fallback_warnings = tuple(
        f"trafilatura found no main content for {url}; used <body> fallback"
        for url, article in zip(config.urls, articles, strict=False)
        if article is not None and article.used_fallback
    )
    return book, result.unresolved_hrefs, fallback_warnings


def build_book_model_from_html(
    html: str, source_url: str, config: BuildConfig
) -> tuple[BookModel, tuple[str, ...], tuple[str, ...]]:
    """Build a BookModel from already-rendered HTML, skipping the fetch step.

    Intended for callers (e.g. a browser extension capture) that already hold the fully
    rendered page HTML and just need it run through extraction, normalization, structuring,
    and metadata resolution.
    """
    overrides = load_metadata_sidecar(Path(config.metadata_path) if config.metadata_path else None)

    article = extract_article(html, source_url)
    stem = article.title or slugify_url(source_url)
    docs = [RawDocument(file_stem=stem, raw_html=article.html_fragment)]
    articles: list[ExtractedArticle | None] = [article]
    raw_pages = [html]

    normalized = [(d.file_stem, normalize_html(d.raw_html), d.raw_html) for d in docs]
    _, frag, _ = normalized[0]
    result = build_from_single_document(frag, config.split_level)

    book = _resolve_metadata_and_build(
        config, overrides, docs, raw_pages, articles, normalized, result, fallback_url=source_url
    )
    fallback_warnings = (
        (f"trafilatura found no main content for {source_url}; used <body> fallback",)
        if article.used_fallback
        else ()
    )
    return book, result.unresolved_hrefs, fallback_warnings


def _resolve_metadata_and_build(
    config: BuildConfig,
    overrides: MetadataOverrides,
    docs: list[RawDocument],
    raw_pages: list[str],
    articles: list[ExtractedArticle | None],
    normalized: list[tuple[str, str, str]],
    result: StructureResult,
    fallback_url: str | None = None,
) -> BookModel:
    """Resolve the metadata ladder for the primary document and assemble the BookModel."""
    fallback_stem = docs[0].file_stem
    scraped_title = scrape_title(raw_pages[0])
    scraped_author = scrape_author(raw_pages[0])
    primary_article = articles[0]
    extracted_title = primary_article.title if primary_article else None
    extracted_author = primary_article.author if primary_article else None
    extracted_date = primary_article.date if primary_article else None
    canonical_url = primary_article.canonical_url if primary_article else None

    url_for_author = canonical_url or (config.urls[0] if config.urls else fallback_url)
    derived_author = _derive_author_from_url(url_for_author) if url_for_author else None

    title = config.title or overrides.title or extracted_title or scraped_title or fallback_stem
    author = (
        config.author or overrides.author or extracted_author or scraped_author or derived_author
    )
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

    return BookModel(
        metadata=metadata,
        chapters=result.chapters,
        toc=result.toc,
        spine=tuple(c.file_name for c in result.chapters),
    )


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


def _derive_author_from_url(url: str) -> str | None:
    """Last-resort author when no byline exists anywhere: the site's domain, title-cased.

    "https://www.tigerdata.com/some-url" -> "Tigerdata". Only used when config, sidecar,
    extraction, and <meta name="author"> scraping all come up empty.
    """
    host = urlsplit(url).netloc.lower().split(":", 1)[0]
    labels = [label for label in host.split(".") if label]
    if labels and labels[0] == "www":
        labels = labels[1:]
    if len(labels) >= 2:
        label = labels[-2]
    elif labels:
        label = labels[0]
    else:
        return None
    if not label or label.isdigit():
        return None
    return label.capitalize()


def slugify_url(url: str) -> str:
    """Derive a filesystem-safe stem from a URL for use as a chapter/file name."""
    slug = re.sub(r"^https?://", "", url)
    slug = re.sub(r"[^A-Za-z0-9]+", "-", slug).strip("-").lower()
    return slug or "page"
