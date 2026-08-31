"""Write a BookModel to a deterministic EPUB 3 file. The only module importing ebooklib."""

from __future__ import annotations

import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from ebooklib import epub

from html_to_epub.models import BookModel, TocNode

_FIXED_DATE_TIME = (2000, 1, 1, 0, 0, 0)
_MODIFIED_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def write_epub(book_model: BookModel, output_path: Path) -> None:
    """Build the EPUB via ebooklib, then post-process it for byte-determinism."""
    book = _build_ebooklib_book(book_model)
    mtime = datetime.strptime(book_model.metadata.modified, _MODIFIED_FORMAT)  # noqa: DTZ007

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / "raw.epub"
        epub.write_epub(str(tmp_path), book, {"epub3_pages": False, "mtime": mtime})
        _rewrite_deterministic(tmp_path, output_path)


def _build_ebooklib_book(book_model: BookModel) -> epub.EpubBook:
    meta = book_model.metadata
    book = epub.EpubBook()
    book.set_identifier(meta.identifier)
    book.set_title(meta.title)
    book.set_language(meta.language)
    if meta.author:
        book.add_author(meta.author)
    if meta.publisher:
        book.add_metadata("DC", "publisher", meta.publisher)
    # dcterms:modified is emitted once by ebooklib itself, driven by the "mtime" write option
    # passed to epub.write_epub() below — do not add a second one here.

    items: dict[str, epub.EpubHtml] = {}
    for chapter in book_model.chapters:
        html_item = epub.EpubHtml(
            uid=chapter.id,
            title=chapter.title,
            file_name=chapter.file_name,
            lang=meta.language,
        )
        # ebooklib/lxml reject Python `str` content that carries an XML encoding declaration
        # (raises internally and is swallowed, yielding a silently empty chapter). Encode to
        # bytes so lxml's HTML parser accepts the declaration.
        html_item.content = (
            f'<?xml version="1.0" encoding="utf-8"?>\n'
            f'<html xmlns="http://www.w3.org/1999/xhtml">\n'
            f"<head><title>{_escape(chapter.title)}</title></head>\n"
            f"<body>{chapter.body_xhtml}</body>\n"
            f"</html>"
        ).encode()
        book.add_item(html_item)
        items[chapter.file_name] = html_item

    nav = epub.EpubNav()
    book.add_item(nav)
    book.add_item(epub.EpubNcx())

    book.toc = tuple(_toc_node_to_link(node) for node in book_model.toc)
    book.spine = ["nav", *[items[fn] for fn in book_model.spine]]

    return book


def _toc_node_to_link(node: TocNode) -> object:
    link = epub.Link(node.href, node.title, node.href)
    if node.children:
        return (link, tuple(_toc_node_to_link(c) for c in node.children))
    return link


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _rewrite_deterministic(src: Path, dst: Path) -> None:
    """Rewrite a zip with fixed timestamps, sorted entry order, mimetype first/stored."""
    with zipfile.ZipFile(src, "r") as zin:
        names = zin.namelist()
        contents = {name: zin.read(name) for name in names}

    ordered = ["mimetype"] + sorted(n for n in names if n != "mimetype")

    with zipfile.ZipFile(dst, "w") as zout:
        for name in ordered:
            data = contents[name]
            info = zipfile.ZipInfo(name, date_time=_FIXED_DATE_TIME)
            info.external_attr = 0o644 << 16
            if name == "mimetype":
                info.compress_type = zipfile.ZIP_STORED
            else:
                info.compress_type = zipfile.ZIP_DEFLATED
            zout.writestr(info, data)


__all__ = ["write_epub"]
