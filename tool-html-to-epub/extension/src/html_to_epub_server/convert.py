"""The only module wrapping html_to_epub's build/validate/write pipeline.

No sanitize, split, TOC, or metadata logic lives here or anywhere else in this package --
it all lives in the parent `html_to_epub` package.
"""

from __future__ import annotations

from pathlib import Path

from html_to_epub.config import BuildConfig
from html_to_epub.epub_writer import write_epub
from html_to_epub.pipeline import build_book_model_from_html
from html_to_epub.validator import validate_model


class ConversionError(Exception):
    """Raised when the captured HTML cannot be converted to a valid EPUB."""


def convert_html_to_epub(
    *,
    html: str,
    url: str,
    output_path: Path,
    title: str | None = None,
    split_level: int = 1,
    language: str = "en",
) -> None:
    """Build a BookModel from captured HTML, validate it, and write it to `output_path`.

    Raises:
        ConversionError: if the HTML yields no content, or structural validation fails.
    """
    if not html or not html.strip():
        raise ConversionError("no content: html body is empty")

    config = BuildConfig(
        input_path=None,
        output_path=str(output_path),
        metadata_path=None,
        title=title,
        author=None,
        language=language,
        identifier=None,
        split_level=split_level,
        urls=(url,),
    )

    book, _unresolved, _warnings = build_book_model_from_html(html, url, config)

    findings = validate_model(book)
    errors = [f for f in findings if f.level == "error"]
    if errors:
        joined = "; ".join(f.message for f in errors)
        raise ConversionError(f"validation failed: {joined}")

    write_epub(book, output_path)


__all__ = ["ConversionError", "convert_html_to_epub"]
