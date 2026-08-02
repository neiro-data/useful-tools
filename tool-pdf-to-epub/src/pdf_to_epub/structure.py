"""Heading inference and chapter/TOC assembly from reading-order blocks. Pure, stdlib-only."""

from __future__ import annotations

import dataclasses
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from pdf_to_epub.config import Thresholds
from pdf_to_epub.models import Chapter, TocNode, Warning
from pdf_to_epub.pdf_source import OutlineEntry
from pdf_to_epub.reconstruct import Block
from pdf_to_epub.xhtml import assert_parseable, heading, paragraph

_TERMINAL_PUNCT = '.?!:"'
_CHAPTER_WORD_RE = re.compile(r"^(chapter|part|section|appendix)\b", re.IGNORECASE)
_ROMAN_ONLY_RE = re.compile(r"^[ivxlcdmIVXLCDM]+$")


@dataclass(frozen=True)
class StructureResult:
    chapters: tuple[Chapter, ...]
    toc: tuple[TocNode, ...]
    warnings: tuple[Warning, ...]
    outline_used: bool


def body_style(blocks: Sequence[Block]) -> tuple[float, str]:
    """Char-count-weighted mode of rounded span sizes/font at that size."""
    size_weight: Counter[float] = Counter()
    for block in blocks:
        if block.kind != "paragraph" or block.font_key is None:
            continue
        size_weight[round(block.font_key[1])] += len(block.text)

    if not size_weight:
        return 0.0, ""
    body_size = size_weight.most_common(1)[0][0]

    font_weight: Counter[str] = Counter()
    for block in blocks:
        if block.kind != "paragraph" or block.font_key is None:
            continue
        if round(block.font_key[1]) == body_size:
            font_weight[block.font_key[0]] += len(block.text)
    body_font = font_weight.most_common(1)[0][0] if font_weight else ""

    return float(body_size), body_font


def _is_bold(font_key: tuple[str, float] | None) -> bool:
    return font_key is not None and "bold" in font_key[0].lower()


def _is_terminal(text: str) -> bool:
    return bool(text) and text.rstrip()[-1:] in _TERMINAL_PUNCT


def _is_size_heading(block: Block, body_size: float, t: Thresholds) -> bool:
    if block.font_key is None or body_size <= 0:
        return False
    size = block.font_key[1]
    if size >= t.heading_size_ratio * body_size:
        return True
    return size >= t.heading_bold_size_ratio * body_size and _is_bold(block.font_key)


def _is_short(text: str, t: Thresholds) -> bool:
    words = text.split()
    lines = text.count("\n") + 1
    return len(words) <= t.heading_max_words and lines <= t.heading_max_lines


def _is_promoted(text: str) -> bool:
    stripped = text.strip()
    return bool(_CHAPTER_WORD_RE.match(stripped) or _ROMAN_ONLY_RE.match(stripped))


def infer_headings(blocks: Sequence[Block], body_size: float, t: Thresholds) -> tuple[Block, ...]:
    """Return ``blocks`` with heading candidates re-tagged (kind='heading', level set)."""
    candidate_idx: list[int] = []
    for i, block in enumerate(blocks):
        if block.kind != "paragraph":
            continue
        promoted = _is_promoted(block.text)
        opener = (
            i > 0
            and blocks[i - 1].pages
            and block.pages
            and blocks[i - 1].pages[-1] != block.pages[0]
            and len(blocks[i - 1].text.split()) <= t.heading_max_words
        )
        size_ok = _is_size_heading(block, body_size, t) and _is_short(block.text, t)
        if not _is_terminal(block.text) and (size_ok or promoted or opener):
            candidate_idx.append(i)

    styles: list[tuple[float, bool]] = []
    for i in candidate_idx:
        block = blocks[i]
        size = block.font_key[1] if block.font_key else body_size
        style = (round(size), _is_bold(block.font_key))
        if style not in styles:
            styles.append(style)
    styles.sort(key=lambda s: (-s[0], not s[1]))
    level_by_style = {style: min(rank + 1, 3) for rank, style in enumerate(styles)}

    result = list(blocks)
    for i in candidate_idx:
        block = blocks[i]
        size = block.font_key[1] if block.font_key else body_size
        style = (round(size), _is_bold(block.font_key))
        level = level_by_style.get(style, 3)
        result[i] = dataclasses.replace(block, kind="heading", level=level)
    return tuple(result)


def _render_block(block: Block, anchor: str | None) -> str:
    if block.kind == "heading":
        return heading(block.level or 3, block.text, anchor or "")
    if block.kind == "table":
        return block.text
    return paragraph(block.text)


def _nest_toc(items: Sequence[tuple[int, str, str]]) -> tuple[TocNode, ...]:
    if not items:
        return ()
    pos = [0]

    def helper(min_level: int) -> list[TocNode]:
        nodes: list[TocNode] = []
        while pos[0] < len(items):
            level, title, href = items[pos[0]]
            if level < min_level:
                break
            pos[0] += 1
            children = helper(level + 1)
            nodes.append(TocNode(title=title, href=href, children=tuple(children)))
        return nodes

    return tuple(helper(items[0][0]))


def build_structure(
    blocks: Sequence[Block],
    outline: Sequence[OutlineEntry],
    split_level: int,
    t: Thresholds,
) -> StructureResult:
    """Split ``blocks`` into chapters at heading boundaries, and build the TOC."""
    body_size, _body_font = body_style(blocks)
    annotated = infer_headings(blocks, body_size, t)
    warnings: list[Warning] = []

    heading_idx = [i for i, b in enumerate(annotated) if b.kind == "heading"]

    if not heading_idx:
        whole_doc_parts = [_render_block(b, None) for b in annotated]
        content = "".join(whole_doc_parts)
        assert_parseable(content)
        pages = tuple(dict.fromkeys(p for b in annotated for p in b.pages))
        chapter = Chapter(
            id="chap_0001",
            title="Untitled",
            file_name="chap_0001.xhtml",
            body_xhtml=content,
            anchors=(),
            source_pages=pages,
        )
        warnings.append(
            Warning(
                code="structure.no_headings",
                message="no headings detected; document emitted as a single chapter",
                page=None,
                severity="warning",
            )
        )
        return StructureResult(
            chapters=(chapter,), toc=(), warnings=tuple(warnings), outline_used=False
        )

    split_levels = {1} if split_level == 1 else {1, 2}
    split_points = sorted({i for i in heading_idx if (annotated[i].level or 3) in split_levels})
    if not split_points or split_points[0] != 0:
        split_points = [0, *split_points]

    chapters: list[Chapter] = []
    heading_records: list[tuple[Block, int, str, str]] = []
    anchor_counter = 0

    for ci, start in enumerate(split_points):
        end = split_points[ci + 1] if ci + 1 < len(split_points) else len(annotated)
        seg = annotated[start:end]
        if not seg:
            continue
        chap_id = f"chap_{ci + 1:04d}"
        file_name = f"{chap_id}.xhtml"
        title_block = next((b for b in seg if b.kind == "heading"), None)
        title = title_block.text if title_block else "Untitled"

        parts: list[str] = []
        anchors: list[str] = []
        for b in seg:
            if b.kind == "heading":
                anchor_counter += 1
                anchor = f"h{anchor_counter}"
                parts.append(_render_block(b, anchor))
                anchors.append(anchor)
                heading_records.append((b, b.level or 3, anchor, file_name))
            else:
                parts.append(_render_block(b, None))
        content = "".join(parts)
        assert_parseable(content)
        pages = tuple(dict.fromkeys(p for b in seg for p in b.pages))
        chapters.append(
            Chapter(
                id=chap_id,
                title=title,
                file_name=file_name,
                body_xhtml=content,
                anchors=tuple(anchors),
                source_pages=pages,
            )
        )

    outline_used = False
    toc: tuple[TocNode, ...] = ()

    if len(outline) >= t.outline_min_entries and heading_records:
        resolved = 0
        outline_items: list[tuple[int, str, str]] = []
        for entry in outline:
            best = min(
                heading_records,
                key=lambda r: min((abs(entry.page - p) for p in r[0].pages), default=10**9),
            )
            dist = min((abs(entry.page - p) for p in best[0].pages), default=10**9)
            href = f"{best[3]}#{best[2]}"
            if dist <= t.outline_resolve_page_tolerance:
                resolved += 1
            outline_items.append((entry.level, entry.title, href))
        if outline and (resolved / len(outline)) >= t.outline_min_resolved_frac:
            outline_used = True
            toc = _nest_toc(outline_items)

    if not outline_used:
        inferred_items = [
            (level, block.text, f"{file_name}#{anchor}")
            for block, level, anchor, file_name in heading_records
            if level in (1, 2)
        ]
        toc = _nest_toc(inferred_items)
        warnings.append(
            Warning(
                code="structure.outline_fallback",
                message="PDF outline missing or unreliable; TOC built from inferred headings",
                page=None,
                severity="warning",
            )
        )

    return StructureResult(
        chapters=tuple(chapters), toc=toc, warnings=tuple(warnings), outline_used=outline_used
    )
