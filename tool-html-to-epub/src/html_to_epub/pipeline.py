"""Orchestrate load -> normalize -> structure -> BookModel."""

from __future__ import annotations

import hashlib
from pathlib import Path

from html_to_epub.config import BuildConfig
from html_to_epub.loaders import (
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


def build_book_model(config: BuildConfig) -> tuple[BookModel, tuple[str, ...]]:
    """Run the full pipeline and return (BookModel, unresolved_hrefs)."""
    input_path = Path(config.input_path)
    is_dir = input_path.is_dir()

    docs = load_documents(input_path)
    overrides = load_metadata_sidecar(Path(config.metadata_path) if config.metadata_path else None)

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

    title = config.title or overrides.title or scrape_title(docs[0].raw_html) or input_path.stem
    author = config.author or overrides.author or scrape_author(docs[0].raw_html)
    language = config.language or overrides.language or "en"
    identifier = config.identifier or overrides.identifier or _content_hash(normalized)
    # EPUB 3 requires dcterms:modified to be a CCYY-MM-DDThh:mm:ssZ timestamp; without a
    # sidecar override there is no meaningful "modified" time, so use a fixed epoch constant
    # rather than datetime.now() (non-deterministic) or a content hash (not a timestamp).
    modified = overrides.date or "1970-01-01T00:00:00Z"

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
    return book, result.unresolved_hrefs


def _content_hash(normalized: list[tuple[str, str, str]], prefix: str = "") -> str:
    hasher = hashlib.blake2b(digest_size=16)
    for stem, frag, _raw in normalized:
        hasher.update(stem.encode("utf-8"))
        hasher.update(frag.encode("utf-8"))
    return f"{prefix}{hasher.hexdigest()}"
