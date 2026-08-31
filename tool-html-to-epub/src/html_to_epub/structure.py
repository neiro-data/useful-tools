"""Split normalized XHTML into chapters and derive a TOC tree.

Deterministic ids/filenames: chap_0001 / chap_0001.xhtml, assigned strictly
in document order. Anchors on headings are used both to build the TOC and
to rewrite same-document href="#x" links to the chapter file that owns #x.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypedDict

from bs4 import BeautifulSoup
from bs4.element import Tag

from html_to_epub.models import Chapter, TocNode
from html_to_epub.normalize import render_node

HEADING_LEVELS = {f"h{n}": n for n in range(1, 7)}


class _TocDict(TypedDict):
    title: str
    href: str
    children: list[_TocDict]


@dataclass(frozen=True)
class InputDoc:
    """One source document feeding the chapter builder (dir mode = one per file)."""

    stem: str
    xhtml_fragment: str
    title: str | None = None


@dataclass
class _ChapterBuilder:
    id: str
    file_name: str
    title: str
    nodes: list[object] = field(default_factory=list)
    anchors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class StructureResult:
    chapters: tuple[Chapter, ...]
    toc: tuple[TocNode, ...]
    unresolved_hrefs: tuple[str, ...]


def _chapter_id(n: int) -> str:
    return f"chap_{n:04d}"


def _chapter_file(n: int) -> str:
    return f"{_chapter_id(n)}.xhtml"


def _ensure_id(tag: Tag, counter: list[int]) -> str:
    existing = tag.get("id")
    if existing:
        return str(existing)
    counter[0] += 1
    new_id = f"h-{counter[0]}"
    tag["id"] = new_id
    return new_id


def build_from_single_document(fragment: str, split_level: int) -> StructureResult:
    """Split one document's fragment into chapters at headings <= split_level."""
    soup = BeautifulSoup(f"<root>{fragment}</root>", "lxml")
    root = soup.find("root")
    top_nodes = list(root.contents) if root else []

    builders: list[_ChapterBuilder] = []
    n = 0
    current: _ChapterBuilder | None = None
    id_counter = [0]
    # heading stack for TOC nesting: list of (level, TocNode-in-progress dict)
    toc_roots: list[_TocDict] = []
    toc_stack: list[tuple[int, _TocDict]] = []

    def start_chapter(title: str) -> _ChapterBuilder:
        nonlocal n, current
        n += 1
        current = _ChapterBuilder(id=_chapter_id(n), file_name=_chapter_file(n), title=title)
        builders.append(current)
        return current

    current = start_chapter("Untitled")

    for node in top_nodes:
        if isinstance(node, Tag) and node.name in HEADING_LEVELS:
            level = HEADING_LEVELS[node.name]
            if level <= split_level:
                title_text = node.get_text(strip=True) or "Untitled"
                if not builders[0].nodes and current is builders[0] and len(builders) == 1:
                    # first split heading immediately: drop the empty leading chapter
                    builders.pop()
                    n -= 1
                current = start_chapter(title_text)
                anchor_id = _ensure_id(node, id_counter)
                current.nodes.append(node)
                current.anchors.append(anchor_id)
                toc_node: _TocDict = {
                    "title": title_text,
                    "href": current.file_name,
                    "children": [],
                }
                toc_roots.append(toc_node)
                toc_stack = [(level, toc_node)]
                continue
            if level >= split_level and current is not None:
                anchor_id = _ensure_id(node, id_counter)
                current.anchors.append(anchor_id)
                title_text = node.get_text(strip=True) or "Untitled"
                toc_node = {
                    "title": title_text,
                    "href": f"{current.file_name}#{anchor_id}",
                    "children": [],
                }
                while toc_stack and toc_stack[-1][0] >= level:
                    toc_stack.pop()
                if toc_stack:
                    toc_stack[-1][1]["children"].append(toc_node)
                else:
                    toc_roots.append(toc_node)
                toc_stack.append((level, toc_node))
                if current is not None:
                    current.nodes.append(node)
                continue
        if current is not None:
            current.nodes.append(node)

    if builders and not builders[0].nodes:
        builders.pop(0)

    return _finalize(builders, toc_roots)


def build_from_directory(docs: list[InputDoc], split_level: int) -> StructureResult:
    """One chapter per input file; internal headings feed the TOC only."""
    builders: list[_ChapterBuilder] = []
    toc_roots: list[_TocDict] = []
    id_counter = [0]

    for n, doc in enumerate(docs, start=1):
        soup = BeautifulSoup(f"<root>{doc.xhtml_fragment}</root>", "lxml")
        root = soup.find("root")
        top_nodes = list(root.contents) if root else []

        title = doc.title or doc.stem
        chapter = _ChapterBuilder(id=_chapter_id(n), file_name=_chapter_file(n), title=title)
        chapter.nodes.extend(top_nodes)
        builders.append(chapter)

        toc_node: _TocDict = {"title": title, "href": chapter.file_name, "children": []}
        toc_roots.append(toc_node)
        toc_stack: list[tuple[int, _TocDict]] = [(0, toc_node)]

        for node in top_nodes:
            if isinstance(node, Tag) and node.name in HEADING_LEVELS:
                level = HEADING_LEVELS[node.name]
                if level < split_level:
                    continue
                anchor_id = _ensure_id(node, id_counter)
                chapter.anchors.append(anchor_id)
                if level == split_level:
                    # already represented by the chapter's own TOC root entry
                    continue
                heading_title = node.get_text(strip=True) or "Untitled"
                child: _TocDict = {
                    "title": heading_title,
                    "href": f"{chapter.file_name}#{anchor_id}",
                    "children": [],
                }
                while toc_stack and toc_stack[-1][0] >= level:
                    toc_stack.pop()
                toc_stack[-1][1]["children"].append(child)
                toc_stack.append((level, child))

    return _finalize(builders, toc_roots)


def _finalize(builders: list[_ChapterBuilder], toc_roots: list[_TocDict]) -> StructureResult:
    chapters = []
    href_owners: dict[str, set[str]] = {}
    for b in builders:
        for node in b.nodes:
            if isinstance(node, Tag):
                node_id = node.get("id")
                if isinstance(node_id, str):
                    href_owners.setdefault(node_id, set()).add(b.file_name)
                for descendant in node.find_all(id=True):
                    descendant_id = descendant.get("id")
                    if isinstance(descendant_id, str):
                        href_owners.setdefault(descendant_id, set()).add(b.file_name)

    unresolved: list[str] = []
    for b in builders:
        body_html = "".join(render_node(node) for node in b.nodes)
        body_html, missing = _rewrite_hrefs(body_html, b.file_name, href_owners)
        unresolved.extend(missing)
        chapters.append(
            Chapter(
                id=b.id,
                title=b.title,
                file_name=b.file_name,
                body_xhtml=body_html,
                anchors=tuple(b.anchors),
            )
        )

    toc = tuple(_dict_to_toc(t) for t in toc_roots)
    return StructureResult(chapters=tuple(chapters), toc=toc, unresolved_hrefs=tuple(unresolved))


def _dict_to_toc(d: _TocDict) -> TocNode:
    return TocNode(
        title=d["title"],
        href=d["href"],
        children=tuple(_dict_to_toc(c) for c in d["children"]),
    )


def _rewrite_hrefs(
    body_html: str, own_file_name: str, href_owners: dict[str, set[str]]
) -> tuple[str, list[str]]:
    soup = BeautifulSoup(f"<root>{body_html}</root>", "lxml")
    root = soup.find("root")
    missing: list[str] = []
    if root:
        for a in root.find_all("a"):
            href = a.get("href")
            if isinstance(href, str) and href.startswith("#"):
                anchor = href[1:]
                owners = href_owners.get(anchor)
                if owners and own_file_name in owners:
                    owner = own_file_name
                elif owners:
                    # cross-chapter: pick deterministically (lowest file name)
                    owner = min(owners)
                    if len(owners) > 1:
                        missing.append(f"{href} (ambiguous, resolved to {owner})")
                else:
                    owner = None
                if owner is not None:
                    a["href"] = f"{owner}#{anchor}"
                else:
                    missing.append(href)
    rewritten = "".join(render_node(child) for child in (root.contents if root else []))
    return rewritten, missing
