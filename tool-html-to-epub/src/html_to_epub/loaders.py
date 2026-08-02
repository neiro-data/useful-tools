"""Load raw HTML documents and optional TOML metadata from disk."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup

HTML_SUFFIXES = {".html", ".xhtml"}


@dataclass(frozen=True)
class RawDocument:
    """A single loaded HTML source file, pre-normalization."""

    file_stem: str
    raw_html: str


@dataclass(frozen=True)
class MetadataOverrides:
    title: str | None = None
    author: str | None = None
    language: str | None = None
    identifier: str | None = None
    date: str | None = None


def load_documents(input_path: Path) -> list[RawDocument]:
    """Load one file, or all HTML files in a directory sorted by filename."""
    if input_path.is_dir():
        files = sorted(p for p in input_path.iterdir() if p.suffix.lower() in HTML_SUFFIXES)
        if not files:
            raise ValueError(f"no HTML files found in directory: {input_path}")
        return [RawDocument(f.stem, f.read_text(encoding="utf-8")) for f in files]

    if input_path.suffix.lower() not in HTML_SUFFIXES:
        raise ValueError(f"unsupported input file type: {input_path}")
    return [RawDocument(input_path.stem, input_path.read_text(encoding="utf-8"))]


def load_metadata_sidecar(metadata_path: Path | None) -> MetadataOverrides:
    """Parse an optional TOML metadata sidecar file."""
    if metadata_path is None:
        return MetadataOverrides()
    with metadata_path.open("rb") as f:
        data = tomllib.load(f)
    return MetadataOverrides(
        title=data.get("title"),
        author=data.get("author"),
        language=data.get("language"),
        identifier=data.get("identifier"),
        date=data.get("date"),
    )


def scrape_title(raw_html: str) -> str | None:
    """Best-effort extraction of <title> or a <meta name="title"> tag."""
    soup = BeautifulSoup(raw_html, "lxml")
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    meta = soup.find("meta", attrs={"name": "title"})
    if meta and meta.get("content"):
        return str(meta["content"]).strip()
    return None


def scrape_author(raw_html: str) -> str | None:
    soup = BeautifulSoup(raw_html, "lxml")
    meta = soup.find("meta", attrs={"name": "author"})
    if meta and meta.get("content"):
        return str(meta["content"]).strip()
    return None
