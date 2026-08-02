"""argparse-based CLI: build, inspect, validate."""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path
from xml.etree.ElementTree import ParseError

from html_to_epub.config import BuildConfig
from html_to_epub.epub_writer import write_epub
from html_to_epub.models import BookModel, TocNode
from html_to_epub.pipeline import build_book_model
from html_to_epub.validator import Finding, validate_epub_file, validate_model


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "build":
        return _cmd_build(args)
    if args.command == "inspect":
        return _cmd_inspect(args)
    if args.command == "validate":
        return _cmd_validate(args)
    parser.print_help()
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="html2epub")
    sub = parser.add_subparsers(dest="command", required=True)

    build_p = sub.add_parser("build", help="Build an EPUB from HTML input")
    build_p.add_argument("input", help="HTML file or directory of HTML files")
    build_p.add_argument("-o", "--output", required=True, help="Output .epub path")
    build_p.add_argument("--metadata", help="TOML metadata sidecar path")
    build_p.add_argument("--title")
    build_p.add_argument("--author")
    build_p.add_argument("--language")
    build_p.add_argument("--identifier")
    build_p.add_argument("--split-level", type=int, choices=[1, 2], default=1)

    inspect_p = sub.add_parser("inspect", help="Print derived chapter/TOC/spine tree")
    inspect_p.add_argument("input", help="HTML file or directory of HTML files")
    inspect_p.add_argument("--metadata", help="TOML metadata sidecar path")
    inspect_p.add_argument("--split-level", type=int, choices=[1, 2], default=1)

    validate_p = sub.add_parser("validate", help="Validate a written .epub file")
    validate_p.add_argument("epub", help="Path to .epub file")

    return parser


def _config_from_args(args: argparse.Namespace, output: str | None = None) -> BuildConfig:
    return BuildConfig(
        input_path=args.input,
        output_path=output,
        metadata_path=getattr(args, "metadata", None),
        title=getattr(args, "title", None),
        author=getattr(args, "author", None),
        language=getattr(args, "language", None),
        identifier=getattr(args, "identifier", None),
        split_level=args.split_level,
    )


def _build_model_or_none(config: BuildConfig) -> tuple[BookModel, tuple[str, ...]] | None:
    try:
        return build_book_model(config)
    except (OSError, ValueError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return None


def _cmd_build(args: argparse.Namespace) -> int:
    config = _config_from_args(args, output=args.output)
    result = _build_model_or_none(config)
    if result is None:
        return 1
    book, unresolved = result

    findings = validate_model(book)
    if unresolved:
        findings.extend(Finding("warning", f"unresolved href: {h}") for h in unresolved)
    errors = [f for f in findings if f.level == "error"]
    for f in findings:
        print(f"[{f.level}] {f.message}", file=sys.stderr)
    if errors:
        return 1

    output_path = Path(args.output)
    write_epub(book, output_path)
    print(f"wrote {output_path}")
    return 0


def _cmd_inspect(args: argparse.Namespace) -> int:
    config = _config_from_args(args)
    result = _build_model_or_none(config)
    if result is None:
        return 1
    book, unresolved = result

    print(f"title: {book.metadata.title}")
    print(f"language: {book.metadata.language}")
    print(f"identifier: {book.metadata.identifier}")
    print("\nchapters:")
    for chapter in book.chapters:
        print(f"  {chapter.id} -> {chapter.file_name}: {chapter.title}")
    print("\ntoc:")
    for node in book.toc:
        _print_toc(node, indent=1)
    print("\nspine:")
    for file_name in book.spine:
        print(f"  {file_name}")
    if unresolved:
        print("\nunresolved hrefs:", file=sys.stderr)
        for href in unresolved:
            print(f"  {href}", file=sys.stderr)
    return 0


def _print_toc(node: TocNode, indent: int) -> None:
    print(f"{'  ' * indent}- {node.title} ({node.href})")
    for child in node.children:
        _print_toc(child, indent + 1)


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
    errors = [f for f in findings if f.level == "error"]
    if errors:
        return 1
    print(f"{args.epub}: valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
