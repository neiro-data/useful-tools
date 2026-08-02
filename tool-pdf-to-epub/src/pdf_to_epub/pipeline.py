"""Full build orchestration: the only module that knows the end-to-end PDF-to-EPUB flow."""

from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path

from pdf_to_epub import ocr, pdf_source, plumber_source
from pdf_to_epub.classify import DocClass, PageClass, classify_document, classify_page
from pdf_to_epub.confidence import score_document, score_page, score_section
from pdf_to_epub.config import BuildConfig
from pdf_to_epub.layout import PageLayout, detect_columns, segment_zones
from pdf_to_epub.models import BookModel, Chapter, Metadata, Warning
from pdf_to_epub.reconstruct import Block, join_document, page_blocks, strip_running_heads
from pdf_to_epub.structure import build_structure
from pdf_to_epub.tables import table_to_xhtml

_FIXED_MODIFIED = "1970-01-01T00:00:00Z"
_DEFAULT_LANGUAGE = "en"


@dataclass(frozen=True)
class ClassifyReport:
    pages: tuple[PageClass, ...]
    doc: DocClass


@dataclass(frozen=True)
class InspectReport:
    doc: DocClass
    pages: tuple[PageClass, ...]
    ocr_used: bool
    tables_detected: int
    tables_omitted: int
    images_omitted: int
    outline_used: bool
    low_confidence_pages: tuple[tuple[int, float], ...]
    low_confidence_sections: tuple[tuple[str, float], ...]
    book: BookModel


@dataclass(frozen=True)
class _Analysis:
    book: BookModel
    doc_class: DocClass
    page_classes: tuple[PageClass, ...]
    ocr_used: bool
    tables_detected: int
    tables_omitted: int
    images_omitted: int
    outline_used: bool
    page_scores: dict[int, float]


def _load_metadata_overrides(metadata_path: Path | None) -> dict[str, str]:
    if metadata_path is None:
        return {}
    with metadata_path.open("rb") as fh:
        data = tomllib.load(fh)
    return {str(k): str(v) for k, v in data.items() if isinstance(v, str)}


def _content_hash(blocks: tuple[Block, ...]) -> str:
    hasher = hashlib.blake2b(digest_size=16)
    for block in blocks:
        hasher.update(block.text.encode("utf-8"))
    return hasher.hexdigest()


def _analyze(config: BuildConfig) -> _Analysis:
    t = config.thresholds
    warnings: list[Warning] = []

    with contextlib.ExitStack() as stack:
        active_path = config.input_path
        pages = pdf_source.load_pages(active_path)
        page_classes = tuple(classify_page(p, t) for p in pages)
        doc_class = classify_document(page_classes, t)

        ocr_used = False
        if doc_class.kind in ("scanned", "mixed"):
            if config.ocr:
                tmp_dir = stack.enter_context(tempfile.TemporaryDirectory())
                dest = Path(tmp_dir) / "ocr.pdf"
                ocr.run_ocr(active_path, dest)
                active_path = dest
                pages = pdf_source.load_pages(active_path)
                page_classes = tuple(classify_page(p, t) for p in pages)
                doc_class = classify_document(page_classes, t)
                ocr_used = True
            else:
                warnings.append(
                    Warning(
                        code="pdf.scanned_without_ocr",
                        message=(
                            "document appears scanned or mixed; rerun with --ocr "
                            "to extract text from image-only pages"
                        ),
                        page=None,
                        severity="error",
                    )
                )

        layouts: list[PageLayout] = []
        for page in pages:
            col_result = detect_columns(page.words, page.width, page.height, t)
            layout = segment_zones(
                page.words, col_result.gutters, page.width, page.height, t, col_result.warnings
            )
            layouts.append(layout)
            for w in layout.warnings:
                warnings.append(
                    Warning(
                        code=w.code,
                        message=f"page {page.number}: {w.message}",
                        page=page.number,
                        severity=w.severity,
                    )
                )

        per_page_blocks = [
            (page, page_blocks(layout, page, t))
            for page, layout in zip(pages, layouts, strict=True)
        ]
        stripped = strip_running_heads(per_page_blocks, t)

        tables_detected = 0
        tables_omitted = 0
        table_rejected_pages: set[int] = set()
        page_tables: dict[int, list[Block]] = {}
        if config.include_tables:
            page_numbers = [page.number for page in pages]
            tables_by_page = plumber_source.extract_tables_for_pages(active_path, page_numbers)
            for page in pages:
                for raw_table in tables_by_page.get(page.number, ()):
                    tables_detected += 1
                    xhtml = table_to_xhtml(raw_table, t)
                    if xhtml is None:
                        tables_omitted += 1
                        table_rejected_pages.add(page.number)
                        continue
                    page_tables.setdefault(page.number, []).append(
                        Block(
                            kind="table",
                            text=xhtml,
                            pages=(page.number,),
                            bbox=raw_table.bbox,
                            font_key=None,
                        )
                    )

        augmented = [
            (page, (*blocks, *page_tables.get(page.number, ()))) for page, blocks in stripped
        ]
        doc_blocks = join_document(augmented)

        outline = pdf_source.load_outline(active_path)
        structure_result = build_structure(doc_blocks, outline, config.split_level, t)
        warnings.extend(structure_result.warnings)

        char_counts = {page.number: page.char_count for page in pages}
        page_scores = {
            page.number: score_page(
                page_class,
                layout,
                ocr_used=ocr_used,
                table_rejected=page.number in table_rejected_pages,
                t=t,
            )
            for page, page_class, layout in zip(pages, page_classes, layouts, strict=True)
        }

        chapters: list[Chapter] = []
        for chapter in structure_result.chapters:
            confidence = score_section(
                page_scores,
                chapter.source_pages,
                char_counts,
                heading_from_outline=structure_result.outline_used,
            )
            chapters.append(dataclasses.replace(chapter, confidence=confidence))

        doc_confidence = score_document(
            [
                (c.confidence, sum(char_counts.get(p, 0) for p in c.source_pages))
                for c in chapters
            ]
        )

        images_omitted = sum(1 for page in pages if page.image_area > 0)
        if images_omitted:
            warnings.append(
                Warning(
                    code="images.omitted",
                    message=f"{images_omitted} image-bearing page(s) omitted from the EPUB "
                    "(v1 outputs text only)",
                    page=None,
                    severity="warning",
                )
            )

        overrides = _load_metadata_overrides(config.metadata_path)
        pdf_meta = pdf_source.load_metadata(active_path)
        title = overrides.get("title") or pdf_meta.get("title") or config.input_path.stem
        author = overrides.get("author") or pdf_meta.get("author") or None
        publisher = overrides.get("publisher") or pdf_meta.get("producer") or None
        language = overrides.get("language") or _DEFAULT_LANGUAGE
        identifier = overrides.get("identifier") or _content_hash(doc_blocks)

        metadata = Metadata(
            identifier=identifier,
            title=title,
            language=language,
            author=author,
            publisher=publisher,
            modified=_FIXED_MODIFIED,
        )

        source_pages = tuple(page.number for page in pages)
        book = BookModel(
            metadata=metadata,
            chapters=tuple(chapters),
            toc=structure_result.toc,
            spine=tuple(c.file_name for c in chapters),
            source_pages=source_pages,
            confidence=doc_confidence,
            warnings=tuple(warnings),
        )

        return _Analysis(
            book=book,
            doc_class=doc_class,
            page_classes=page_classes,
            ocr_used=ocr_used,
            tables_detected=tables_detected,
            tables_omitted=tables_omitted,
            images_omitted=images_omitted,
            outline_used=structure_result.outline_used,
            page_scores=page_scores,
        )
    raise AssertionError("unreachable")  # pragma: no cover - ExitStack always returns above


def build_book_model(config: BuildConfig) -> BookModel:
    """Run the full PDF-to-EPUB pipeline and return the resulting BookModel."""
    return _analyze(config).book


def classify_document_report(config: BuildConfig) -> ClassifyReport:
    """Classify a PDF's pages and overall kind without running the full pipeline."""
    t = config.thresholds
    pages = pdf_source.load_pages(config.input_path)
    page_classes = tuple(classify_page(p, t) for p in pages)
    doc_class = classify_document(page_classes, t)
    return ClassifyReport(pages=page_classes, doc=doc_class)


def inspect_document(config: BuildConfig) -> InspectReport:
    """Run the full pipeline and return a report suitable for the ``inspect`` CLI command."""
    analysis = _analyze(config)
    book = analysis.book

    low_confidence_pages = tuple(
        sorted(
            ((page, score) for page, score in analysis.page_scores.items() if score < 1.0),
            key=lambda item: item[1],
        )
    )
    low_confidence_sections = tuple(
        sorted(
            ((c.id, c.confidence) for c in book.chapters if c.confidence < 1.0),
            key=lambda item: item[1],
        )
    )

    return InspectReport(
        doc=analysis.doc_class,
        pages=analysis.page_classes,
        ocr_used=analysis.ocr_used,
        tables_detected=analysis.tables_detected,
        tables_omitted=analysis.tables_omitted,
        images_omitted=analysis.images_omitted,
        outline_used=analysis.outline_used,
        low_confidence_pages=low_confidence_pages,
        low_confidence_sections=low_confidence_sections,
        book=book,
    )


__all__ = [
    "ClassifyReport",
    "InspectReport",
    "build_book_model",
    "classify_document_report",
    "inspect_document",
]
