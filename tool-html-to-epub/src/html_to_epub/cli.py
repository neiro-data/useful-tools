"""argparse-based CLI: build, inspect, validate."""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path
from xml.etree.ElementTree import ParseError

from html_to_epub.config import BuildConfig
from html_to_epub.epub_writer import write_epub
from html_to_epub.extract import extract_article
from html_to_epub.fetch import fetch_url
from html_to_epub.models import BookModel, TocNode
from html_to_epub.pipeline import build_book_model, slugify_url
from html_to_epub.validator import Finding, validate_epub_file, validate_model

_URL_SCHEME_RE = re.compile(r"^([a-zA-Z][a-zA-Z0-9+.-]*)://")


def _url_scheme(value: str) -> str | None:
    """Return the `<scheme>` of `value` if it has the shape `<scheme>://...`, else None.

    A local path (bare filename, relative path, or Windows `C:\\...` path) never matches:
    none of those contain `://`.
    """
    match = _URL_SCHEME_RE.match(value)
    return match.group(1).lower() if match else None


def _is_url(value: str) -> bool:
    return _url_scheme(value) in ("http", "https")


def _read_url_list(path: str) -> list[str]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "build":
        return _cmd_build(args)
    if args.command == "inspect":
        return _cmd_inspect(args)
    if args.command == "validate":
        return _cmd_validate(args)
    if args.command == "fetch":
        return _cmd_fetch(args)
    parser.print_help()
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="html2epub")
    sub = parser.add_subparsers(dest="command", required=True)

    build_p = sub.add_parser("build", help="Build an EPUB from HTML input")
    build_p.add_argument("input", nargs="?", help="HTML file, directory, or http(s):// URL")
    build_p.add_argument("-o", "--output", required=True, help="Output .epub path")
    build_p.add_argument("--metadata", help="TOML metadata sidecar path")
    build_p.add_argument("--title")
    build_p.add_argument("--author")
    build_p.add_argument("--language")
    build_p.add_argument("--identifier")
    build_p.add_argument("--split-level", type=int, choices=[1, 2], default=1)
    build_p.add_argument("--url-list", help="File with one URL per line (# comments allowed)")
    build_p.add_argument("--timeout", type=float, default=20.0, help="Fetch timeout in seconds")
    build_p.add_argument("--user-agent", help="HTTP User-Agent header for fetching URLs")

    inspect_p = sub.add_parser("inspect", help="Print derived chapter/TOC/spine tree")
    inspect_p.add_argument("input", nargs="?", help="HTML file, directory, or http(s):// URL")
    inspect_p.add_argument("--metadata", help="TOML metadata sidecar path")
    inspect_p.add_argument("--split-level", type=int, choices=[1, 2], default=1)
    inspect_p.add_argument("--url-list", help="File with one URL per line (# comments allowed)")
    inspect_p.add_argument("--timeout", type=float, default=20.0, help="Fetch timeout in seconds")
    inspect_p.add_argument("--user-agent", help="HTTP User-Agent header for fetching URLs")

    validate_p = sub.add_parser("validate", help="Validate a written .epub file")
    validate_p.add_argument("epub", help="Path to .epub file")

    fetch_p = sub.add_parser("fetch", help="Fetch URL(s) and save extracted content as HTML")
    fetch_p.add_argument("url", nargs="?", help="http(s):// URL to fetch")
    fetch_p.add_argument("--url-list", help="File with one URL per line (# comments allowed)")
    fetch_p.add_argument("-o", "--output", required=True, help="Output directory")
    fetch_p.add_argument("--timeout", type=float, default=20.0, help="Fetch timeout in seconds")
    fetch_p.add_argument("--user-agent", help="HTTP User-Agent header for fetching URLs")

    return parser


def _resolve_urls(args: argparse.Namespace, positional: str | None) -> list[str]:
    url_list = getattr(args, "url_list", None)
    urls = list(_read_url_list(url_list)) if url_list else []
    if positional:
        scheme = _url_scheme(positional)
        if scheme in ("http", "https"):
            urls.insert(0, positional)
        elif scheme is not None:
            raise ValueError(f"unsupported URL scheme: {scheme} (only http/https)")
        elif url_list:
            # Positional is a local path, not a URL, but --url-list was also given: pick one.
            raise ValueError("cannot combine a local input path with --url-list")
    return urls


def _config_from_args(args: argparse.Namespace, output: str | None = None) -> BuildConfig:
    urls = _resolve_urls(args, args.input)
    input_path = None if urls else args.input
    return BuildConfig(
        input_path=input_path,
        output_path=output,
        metadata_path=getattr(args, "metadata", None),
        title=getattr(args, "title", None),
        author=getattr(args, "author", None),
        language=getattr(args, "language", None),
        identifier=getattr(args, "identifier", None),
        split_level=args.split_level,
        urls=tuple(urls),
        timeout=args.timeout,
        user_agent=getattr(args, "user_agent", None),
    )


def _build_model_or_none(
    config: BuildConfig,
) -> tuple[BookModel, tuple[str, ...], tuple[str, ...]] | None:
    try:
        return build_book_model(config)
    except (OSError, ValueError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return None


def _config_or_none(args: argparse.Namespace, output: str | None = None) -> BuildConfig | None:
    try:
        return _config_from_args(args, output=output)
    except (OSError, ValueError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return None


def _cmd_build(args: argparse.Namespace) -> int:
    config = _config_or_none(args, output=args.output)
    if config is None:
        return 1
    result = _build_model_or_none(config)
    if result is None:
        return 1
    book, unresolved, fallback_warnings = result

    findings = validate_model(book)
    if unresolved:
        findings.extend(Finding("warning", f"unresolved href: {h}") for h in unresolved)
    findings.extend(Finding("warning", w) for w in fallback_warnings)
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
    config = _config_or_none(args)
    if config is None:
        return 1
    result = _build_model_or_none(config)
    if result is None:
        return 1
    book, unresolved, fallback_warnings = result
    for w in fallback_warnings:
        print(f"[warning] {w}", file=sys.stderr)

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


def _cmd_fetch(args: argparse.Namespace) -> int:
    try:
        urls = _resolve_urls(args, args.url)
    except ValueError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
    if not urls:
        print("[error] no URLs given (pass a URL or --url-list)", file=sys.stderr)
        return 1

    output_dir = Path(args.output)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        for index, url in enumerate(urls):
            page = fetch_url(url, timeout=args.timeout, user_agent=args.user_agent)
            article = extract_article(page.html, page.final_url)
            slug = slugify_url(page.final_url)
            file_path = output_dir / f"{index:04d}-{slug}.html"
            file_path.write_text(article.html_fragment, encoding="utf-8")
    except (OSError, ValueError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    print(f"wrote {len(urls)} file(s) to {output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
