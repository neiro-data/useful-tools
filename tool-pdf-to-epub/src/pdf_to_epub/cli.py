"""argparse-based CLI: build, inspect, classify, validate."""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path
from xml.etree.ElementTree import ParseError

from pdf_to_epub.config import BuildConfig
from pdf_to_epub.epub_writer import write_epub
from pdf_to_epub.ocr import OcrError
from pdf_to_epub.pdf_source import PdfSourceError
from pdf_to_epub.pipeline import classify_document_report, inspect_document
from pdf_to_epub.validator import validate_epub_file, validate_model


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "build":
        return _cmd_build(args)
    if args.command == "inspect":
        return _cmd_inspect(args)
    if args.command == "classify":
        return _cmd_classify(args)
    if args.command == "validate":
        return _cmd_validate(args)
    parser.print_help()
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pdf2epub")
    sub = parser.add_subparsers(dest="command", required=True)

    build_p = sub.add_parser("build", help="Build an EPUB from a PDF file")
    build_p.add_argument("input", help="Input .pdf path")
    build_p.add_argument("-o", "--output", required=True, help="Output .epub path")
    build_p.add_argument("--ocr", action="store_true", help="Run OCR on scanned/mixed input")
    build_p.add_argument("--split-level", type=int, choices=[1, 2, 3], default=1)
    build_p.add_argument("--min-confidence", type=float, default=0.35)
    build_p.add_argument("--metadata", help="TOML metadata sidecar path")
    build_p.add_argument("--no-tables", action="store_true", help="Skip table extraction")

    inspect_p = sub.add_parser("inspect", help="Print derived pages/chapters/confidence")
    inspect_p.add_argument("input", help="Input .pdf path")
    inspect_p.add_argument("--ocr", action="store_true")
    inspect_p.add_argument("--split-level", type=int, choices=[1, 2, 3], default=1)
    inspect_p.add_argument("--min-confidence", type=float, default=0.35)
    inspect_p.add_argument("--metadata", help="TOML metadata sidecar path")
    inspect_p.add_argument("--no-tables", action="store_true")

    classify_p = sub.add_parser("classify", help="Print per-page and document classification")
    classify_p.add_argument("input", help="Input .pdf path")

    validate_p = sub.add_parser("validate", help="Validate a written .epub file")
    validate_p.add_argument("epub", help="Path to .epub file")

    return parser


def _config_from_args(args: argparse.Namespace, output: str | None = None) -> BuildConfig:
    return BuildConfig(
        input_path=Path(args.input),
        output_path=Path(output) if output else Path("out.epub"),
        ocr=getattr(args, "ocr", False),
        split_level=getattr(args, "split_level", 1),
        min_confidence=getattr(args, "min_confidence", 0.35),
        include_tables=not getattr(args, "no_tables", False),
        metadata_path=Path(args.metadata) if getattr(args, "metadata", None) else None,
    )


def _config_or_none(args: argparse.Namespace, output: str | None = None) -> BuildConfig | None:
    try:
        return _config_from_args(args, output=output)
    except (OSError, ValueError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return None


def _print_confidence_report(report: object) -> None:
    from pdf_to_epub.pipeline import InspectReport  # local import to avoid cycle in type checks

    assert isinstance(report, InspectReport)  # noqa: S101 - internal invariant, not user input
    print(f"OCR used: {'yes' if report.ocr_used else 'no'}", file=sys.stderr)

    kind_counts: dict[str, int] = {}
    for page in report.pages:
        kind_counts[str(page.kind)] = kind_counts.get(str(page.kind), 0) + 1
    print(f"pages by kind: {kind_counts}", file=sys.stderr)
    print(f"columns detected: {report.doc.columns}", file=sys.stderr)
    print(
        f"tables detected: {report.tables_detected}, omitted: {report.tables_omitted}",
        file=sys.stderr,
    )
    print(f"images omitted: {report.images_omitted}", file=sys.stderr)
    toc_source = "outline" if report.outline_used else "inferred headings"
    print(f"TOC source: {toc_source}", file=sys.stderr)

    if report.low_confidence_pages:
        print("low-confidence pages:", file=sys.stderr)
        for page_number, score in report.low_confidence_pages:
            print(f"  page {page_number}: {score:.2f}", file=sys.stderr)
    if report.low_confidence_sections:
        print("low-confidence sections:", file=sys.stderr)
        for chap_id, score in report.low_confidence_sections:
            print(f"  {chap_id}: {score:.2f}", file=sys.stderr)


def _cmd_build(args: argparse.Namespace) -> int:
    config = _config_or_none(args, output=args.output)
    if config is None:
        return 1

    try:
        report = inspect_document(config)
    except (OSError, ValueError, PdfSourceError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
    except OcrError as exc:
        print(f"[error] OCR failed: {exc}", file=sys.stderr)
        return 1

    book = report.book
    _print_confidence_report(report)

    findings = validate_model(book)
    for f in findings:
        print(f"[{f.level}] {f.message}", file=sys.stderr)
    has_error = any(f.level == "error" for f in findings)

    if not any(c.body_xhtml.strip() for c in book.chapters):
        print("[error] zero characters extracted from input", file=sys.stderr)
        has_error = True

    if book.confidence < config.min_confidence:
        print(
            f"[error] document confidence {book.confidence:.2f} below "
            f"--min-confidence {config.min_confidence:.2f}",
            file=sys.stderr,
        )
        has_error = True

    if has_error:
        return 1

    output_path = Path(args.output)
    write_epub(book, output_path)

    epub_findings = validate_epub_file(output_path)
    for f in epub_findings:
        print(f"[{f.level}] {f.message}", file=sys.stderr)
    if any(f.level == "error" for f in epub_findings):
        return 1

    print(f"wrote {output_path}")
    return 0


def _cmd_inspect(args: argparse.Namespace) -> int:
    config = _config_or_none(args)
    if config is None:
        return 1
    try:
        report = inspect_document(config)
    except (OSError, ValueError, PdfSourceError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
    except OcrError as exc:
        print(f"[error] OCR failed: {exc}", file=sys.stderr)
        return 1

    book = report.book
    print("pages:")
    for page in report.pages:
        print(f"  page {page.number}: kind={page.kind} columns={page.columns} "
              f"chars={page.char_count}")
    print("\nchapters:")
    for chapter in book.chapters:
        print(f"  {chapter.id} -> {chapter.file_name}: {chapter.title} "
              f"(confidence={chapter.confidence:.2f})")
    print(f"\ndocument confidence: {book.confidence:.2f}")
    _print_confidence_report(report)
    return 0


def _cmd_classify(args: argparse.Namespace) -> int:
    config = _config_or_none(args)
    if config is None:
        return 1
    try:
        report = classify_document_report(config)
    except (OSError, ValueError, PdfSourceError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    print(f"document kind: {report.doc.kind}")
    print(f"document columns: {report.doc.columns}")
    print("pages:")
    for page in report.pages:
        print(
            f"  page {page.number}: kind={page.kind} columns={page.columns} "
            f"chars={page.char_count} words={page.word_count}"
        )
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    epub_path = Path(args.epub)
    if not epub_path.exists():
        print(f"[error] file not found: {epub_path}", file=sys.stderr)
        return 1
    try:
        findings = validate_epub_file(epub_path)
    except (zipfile.BadZipFile, ParseError) as exc:
        print(f"[error] not a valid EPUB file: {exc}", file=sys.stderr)
        return 1
    for f in findings:
        print(f"[{f.level}] {f.message}", file=sys.stderr)
    if any(f.level == "error" for f in findings):
        return 1
    print(f"{args.epub}: valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
