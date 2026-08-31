"""Validate a BookModel before write, or a written .epub file after write."""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

from pdf_to_epub.models import BookModel, TocNode

OPF_NS = "{http://www.idpf.org/2007/opf}"


@dataclass(frozen=True)
class Finding:
    level: str  # "error" | "warning"
    message: str


def validate_model(book: BookModel) -> list[Finding]:
    """Structural checks against the internal BookModel, before writing."""
    findings: list[Finding] = []
    meta = book.metadata

    if not meta.identifier.strip():
        findings.append(Finding("error", "metadata.identifier is empty"))
    if not meta.title.strip():
        findings.append(Finding("error", "metadata.title is empty"))
    if not meta.language.strip():
        findings.append(Finding("error", "metadata.language is empty"))

    chapter_files = {c.file_name for c in book.chapters}
    for file_name in book.spine:
        if file_name not in chapter_files:
            findings.append(Finding("error", f"spine references unknown chapter: {file_name}"))

    for chapter in book.chapters:
        if not chapter.body_xhtml.strip():
            findings.append(Finding("error", f"chapter {chapter.file_name} has empty body"))

    anchor_ids: dict[str, set[str]] = {c.file_name: set(c.anchors) for c in book.chapters}

    def check_toc(nodes: tuple[TocNode, ...]) -> None:
        for node in nodes:
            href = node.href
            file_part, _, anchor = href.partition("#")
            if file_part not in chapter_files:
                findings.append(Finding("error", f"TOC href resolves to unknown file: {href}"))
            elif anchor and anchor not in anchor_ids.get(file_part, set()):
                findings.append(Finding("error", f"TOC anchor not found: {href}"))
            check_toc(node.children)

    check_toc(book.toc)

    for warning in book.warnings:
        findings.append(Finding(warning.severity, warning.message))

    return findings


def validate_epub_file(epub_path: Path) -> list[Finding]:
    """Re-open a written .epub zip and check its structural invariants."""
    findings: list[Finding] = []

    with zipfile.ZipFile(epub_path, "r") as zf:
        names = zf.namelist()
        if not names or names[0] != "mimetype":
            findings.append(Finding("error", "mimetype is not the first zip entry"))
        if "mimetype" not in names:
            findings.append(Finding("error", "mimetype entry missing"))
        else:
            info = zf.getinfo("mimetype")
            if info.compress_type != zipfile.ZIP_STORED:
                findings.append(Finding("error", "mimetype entry must be stored uncompressed"))
            content = zf.read("mimetype").decode("ascii", errors="replace")
            if content != "application/epub+zip":
                findings.append(Finding("error", f"unexpected mimetype content: {content!r}"))

        opf_path = _find_opf_path(zf, names, findings)
        if opf_path is None:
            return findings

        opf_data = zf.read(opf_path)
        try:
            root = ET.fromstring(opf_data)  # noqa: S314 - reading our own generated file
        except ET.ParseError as exc:
            findings.append(Finding("error", f"content.opf is not well-formed XML: {exc}"))
            return findings

        manifest = root.find(f"{OPF_NS}manifest")
        spine = root.find(f"{OPF_NS}spine")
        metadata_el = root.find(f"{OPF_NS}metadata")

        manifest_ids: dict[str, str] = {}
        nav_present = False
        if manifest is not None:
            for item in manifest.findall(f"{OPF_NS}item"):
                item_id = item.get("id")
                href = item.get("href")
                if item_id and href:
                    manifest_ids[item_id] = href
                if item.get("properties") == "nav":
                    nav_present = True
        if not nav_present:
            findings.append(Finding("error", 'no manifest item with properties="nav"'))

        opf_dir = "/".join(opf_path.split("/")[:-1])
        if spine is not None:
            for itemref in spine.findall(f"{OPF_NS}itemref"):
                idref = itemref.get("idref")
                if idref not in manifest_ids:
                    findings.append(Finding("error", f"spine idref not in manifest: {idref}"))
                    continue
                href = manifest_ids[idref]
                item_path = f"{opf_dir}/{href}" if opf_dir else href
                findings.extend(_check_spine_item_content(zf, item_path))

        if metadata_el is None:
            findings.append(Finding("error", "content.opf missing <metadata>"))

    return findings


def _check_spine_item_content(zf: zipfile.ZipFile, item_path: str) -> list[Finding]:
    """Read a spine item out of the archive and reject it if empty or not well-formed XML."""
    findings: list[Finding] = []
    try:
        data = zf.read(item_path)
    except KeyError:
        findings.append(Finding("error", f"spine item missing from archive: {item_path}"))
        return findings

    if not data.strip():
        findings.append(Finding("error", f"spine item is empty: {item_path}"))
        return findings

    try:
        ET.fromstring(data)  # noqa: S314 - reading our own generated file
    except ET.ParseError as exc:
        findings.append(Finding("error", f"spine item is not well-formed XML: {item_path}: {exc}"))

    return findings


def _find_opf_path(zf: zipfile.ZipFile, names: list[str], findings: list[Finding]) -> str | None:
    if "META-INF/container.xml" not in names:
        findings.append(Finding("error", "META-INF/container.xml missing"))
        return None
    container = ET.fromstring(zf.read("META-INF/container.xml"))  # noqa: S314
    ns = "{urn:oasis:names:tc:opendocument:xmlns:container}"
    rootfile = container.find(f"{ns}rootfiles/{ns}rootfile")
    if rootfile is None or not rootfile.get("full-path"):
        findings.append(Finding("error", "container.xml has no rootfile"))
        return None
    return rootfile.get("full-path")
