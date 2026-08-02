"""PDF raw-content extraction. Sole importer of ``fitz`` in this library."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz

_BOLD_FLAG = 1 << 4


class PdfSourceError(Exception):
    """Raised when a PDF cannot be opened or read via PyMuPDF."""


@dataclass(frozen=True)
class Word:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    font: str
    size: float
    bold: bool


@dataclass(frozen=True)
class Span:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    font: str
    size: float
    bold: bool


@dataclass(frozen=True)
class Line:
    spans: tuple[Span, ...]
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass(frozen=True)
class ImageRect:
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass(frozen=True)
class PageRaw:
    number: int
    width: float
    height: float
    words: tuple[Word, ...]
    image_area: float
    text_area: float
    char_count: int
    font_keys: frozenset[tuple[str, float]]


@dataclass(frozen=True)
class OutlineEntry:
    title: str
    level: int
    page: int


def _bold_from_flags(flags: int) -> bool:
    return bool(flags & _BOLD_FLAG)


def _extract_words_with_style(page: fitz.Page) -> tuple[Word, ...]:
    """Build word-level records by pairing PyMuPDF's word boxes with span styling."""
    spans: list[Span] = []
    raw = page.get_text("dict")
    for block in raw.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                bbox = span.get("bbox", (0.0, 0.0, 0.0, 0.0))
                spans.append(
                    Span(
                        text=span.get("text", ""),
                        x0=float(bbox[0]),
                        y0=float(bbox[1]),
                        x1=float(bbox[2]),
                        y1=float(bbox[3]),
                        font=span.get("font", ""),
                        size=float(span.get("size", 0.0)),
                        bold=_bold_from_flags(int(span.get("flags", 0))),
                    )
                )

    raw_words = page.get_text("words")
    words: list[Word] = []
    for w in raw_words:
        x0, y0, x1, y1, text = float(w[0]), float(w[1]), float(w[2]), float(w[3]), str(w[4])
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        best: Span | None = None
        for span in spans:
            if span.x0 - 1 <= cx <= span.x1 + 1 and span.y0 - 1 <= cy <= span.y1 + 1:
                best = span
                break
        font = best.font if best else ""
        size = best.size if best else 0.0
        bold = best.bold if best else False
        words.append(Word(text=text, x0=x0, y0=y0, x1=x1, y1=y1, font=font, size=size, bold=bold))
    return tuple(words)


def _image_area(page: fitz.Page) -> float:
    area = 0.0
    for img in page.get_images(full=True):
        xref = img[0]
        rects = page.get_image_rects(xref)
        for rect in rects:
            area += abs(rect.width * rect.height)
    return area


def load_pages(path: Path) -> tuple[PageRaw, ...]:
    """Load every page of ``path`` into pure-stdlib ``PageRaw`` records."""
    try:
        doc = fitz.open(path)
    except RuntimeError as exc:
        raise PdfSourceError(f"cannot open PDF {path}: {exc}") from exc
    try:
        pages: list[PageRaw] = []
        for index in range(doc.page_count):
            page = doc[index]
            width, height = float(page.rect.width), float(page.rect.height)
            words = _extract_words_with_style(page)
            char_count = sum(len(w.text) for w in words)
            text_area = sum(max(0.0, w.x1 - w.x0) * max(0.0, w.y1 - w.y0) for w in words)
            image_area = _image_area(page)
            page_area = max(width * height, 1e-9)
            font_keys = frozenset((w.font, w.size) for w in words if w.font)
            pages.append(
                PageRaw(
                    number=index + 1,
                    width=width,
                    height=height,
                    words=words,
                    image_area=image_area / page_area,
                    text_area=text_area / page_area,
                    char_count=char_count,
                    font_keys=font_keys,
                )
            )
        return tuple(pages)
    finally:
        doc.close()


def load_outline(path: Path) -> tuple[OutlineEntry, ...]:
    """Load the PDF's bookmark outline, resolving each entry to a 1-based page number."""
    try:
        doc = fitz.open(path)
    except RuntimeError as exc:
        raise PdfSourceError(f"cannot open PDF {path}: {exc}") from exc
    try:
        toc = doc.get_toc(simple=True)
        return tuple(
            OutlineEntry(title=str(title), level=int(level), page=int(page))
            for level, title, page in toc
        )
    finally:
        doc.close()


def load_metadata(path: Path) -> dict[str, str]:
    """Load the PDF document info dictionary as plain strings."""
    try:
        doc = fitz.open(path)
    except RuntimeError as exc:
        raise PdfSourceError(f"cannot open PDF {path}: {exc}") from exc
    try:
        meta = doc.metadata or {}
        return {str(k): str(v) for k, v in meta.items() if v}
    finally:
        doc.close()
