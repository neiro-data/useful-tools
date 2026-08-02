"""Reading-order reconstruction of paragraphs/headings from layout zones. Pure, stdlib-only."""

from __future__ import annotations

import re
import statistics
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from pdf_to_epub.config import Thresholds
from pdf_to_epub.layout import PageLayout, Zone
from pdf_to_epub.pdf_source import PageRaw, Word

_BULLET_RE = re.compile(r"^[•●◦\-\*–]\s")
_NUMBER_PREFIX_RE = re.compile(r"^\d+[.)]\s")
_TERMINAL_PUNCT = '.?!:"'
_HYPHENS = "-‐"
_DIGITS_ONLY_RE = re.compile(r"^\d+$")
_PAGE_NUM_RE = re.compile(r"^(page\s+)?\d+$", re.IGNORECASE)
_ROMAN_RE = re.compile(r"^[ivxlcdmIVXLCDM]+$")


@dataclass(frozen=True)
class Block:
    kind: str
    text: str
    pages: tuple[int, ...]
    bbox: tuple[float, float, float, float]
    font_key: tuple[str, float] | None
    level: int | None = None


@dataclass(frozen=True)
class _LineRec:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    font_key: tuple[str, float] | None


def _line_font_key(words: Sequence[Word]) -> tuple[str, float] | None:
    if not words:
        return None
    counts: dict[tuple[str, float], int] = {}
    for w in words:
        if not w.font:
            continue
        key = (w.font, w.size)
        counts[key] = counts.get(key, 0) + 1
    if not counts:
        return None
    return max(counts.items(), key=lambda kv: kv[1])[0]


def _words_to_lines(words: Sequence[Word], t: Thresholds) -> list[_LineRec]:
    if not words:
        return []
    sorted_words = sorted(words, key=lambda w: (w.y0, w.x0))
    heights = [w.y1 - w.y0 for w in sorted_words if w.y1 > w.y0]
    median_h = statistics.median(heights) if heights else 1.0
    tolerance = t.line_y_tolerance_frac * median_h

    rows: list[list[Word]] = []
    for w in sorted_words:
        placed = False
        for row in rows:
            if abs(w.y0 - row[-1].y0) <= tolerance:
                row.append(w)
                placed = True
                break
        if not placed:
            rows.append([w])

    lines: list[_LineRec] = []
    for row in rows:
        row.sort(key=lambda w: w.x0)
        text = " ".join(w.text for w in row)
        x0 = min(w.x0 for w in row)
        x1 = max(w.x1 for w in row)
        y0 = min(w.y0 for w in row)
        y1 = max(w.y1 for w in row)
        lines.append(_LineRec(text=text, x0=x0, y0=y0, x1=x1, y1=y1, font_key=_line_font_key(row)))
    lines.sort(key=lambda ln: (ln.y0, ln.x0))
    return lines


def _zone_blocks(zone: Zone, page_number: int, t: Thresholds) -> tuple[Block, ...]:
    lines = _words_to_lines(zone.words, t)
    if not lines:
        return ()

    indents = [ln.x0 for ln in lines]
    median_indent = statistics.median(indents)
    gaps = [lines[i + 1].y0 - lines[i].y1 for i in range(len(lines) - 1)]
    median_gap = statistics.median(gaps) if gaps else 0.0
    widths = [ln.x1 - ln.x0 for ln in lines]
    median_width = statistics.median(widths) if widths else 1.0

    blocks: list[Block] = []
    current_lines: list[_LineRec] = []

    def flush() -> None:
        if not current_lines:
            return
        text = " ".join(ln.text for ln in current_lines)
        keys = [ln.font_key for ln in current_lines if ln.font_key]
        font_key = (
            min(Counter(keys).items(), key=lambda kv: (-kv[1], kv[0]))[0] if keys else None
        )
        bbox = (
            min(ln.x0 for ln in current_lines),
            min(ln.y0 for ln in current_lines),
            max(ln.x1 for ln in current_lines),
            max(ln.y1 for ln in current_lines),
        )
        blocks.append(
            Block(
                kind="paragraph",
                text=text,
                pages=(page_number,),
                bbox=bbox,
                font_key=font_key,
            )
        )

    for i, line in enumerate(lines):
        is_new_para = False
        if i == 0:
            is_new_para = True
        else:
            prev = lines[i - 1]
            indent_gap = line.x0 - median_indent
            gap = line.y0 - prev.y1
            prev_short = (prev.x1 - prev.x0) < t.para_short_line_frac * median_width
            prev_ends_terminal = bool(prev.text) and prev.text.rstrip()[-1:] in _TERMINAL_PUNCT
            if (
                indent_gap > t.para_indent_frac * median_indent
                or (median_gap > 0 and gap > t.para_gap_frac * median_gap)
                or _BULLET_RE.match(line.text)
                or _NUMBER_PREFIX_RE.match(line.text)
                or (prev_ends_terminal and prev_short)
            ):
                is_new_para = True

        if is_new_para and current_lines:
            flush()
            current_lines = []
        current_lines.append(line)

    flush()
    return tuple(blocks)


def page_blocks(layout: PageLayout, page: PageRaw, t: Thresholds) -> tuple[Block, ...]:
    """Build reading-order blocks for one page: bands top-to-bottom, zones column-major."""
    by_band: dict[int, list[Zone]] = {}
    for zone in layout.zones:
        by_band.setdefault(zone.band_idx, []).append(zone)

    blocks: list[Block] = []
    for band_idx in sorted(by_band):
        zones = sorted(by_band[band_idx], key=lambda z: z.column_idx)
        for zone in zones:
            blocks.extend(_zone_blocks(zone, page.number, t))
    return tuple(blocks)


def _normalise(line: str) -> str:
    return re.sub(r"\d+", "#", line.strip().lower())


def strip_running_heads(
    pages: Sequence[tuple[PageRaw, tuple[Block, ...]]], t: Thresholds
) -> tuple[tuple[PageRaw, tuple[Block, ...]], ...]:
    """Remove running headers/footers and bare page numbers from band-edge lines."""
    if len(pages) < t.running_head_min_pages:
        return tuple(pages)

    # signature -> parity -> list of (page_index, y_frac)
    odd_sig: dict[str, list[tuple[int, float]]] = {}
    even_sig: dict[str, list[tuple[int, float]]] = {}

    page_line_info: list[list[tuple[Block, float, bool]]] = []

    for page_idx, (page, blocks) in enumerate(pages):
        infos: list[tuple[Block, float, bool]] = []
        for block in blocks:
            y0, y1 = block.bbox[1], block.bbox[3]
            height = page.height or 1.0
            in_top = y0 <= t.running_head_band_frac * height
            in_bottom = y1 >= (1 - t.running_head_band_frac) * height
            if not (in_top or in_bottom):
                continue
            y_frac = ((y0 + y1) / 2) / height
            infos.append((block, y_frac, in_top))
            sig = _normalise(block.text)
            table = even_sig if page_idx % 2 == 0 else odd_sig
            table.setdefault(sig, []).append((page_idx, y_frac))
        page_line_info.append(infos)

    n_pages = len(pages)

    def qualifies(sig: str) -> bool:
        for table in (odd_sig, even_sig):
            entries = table.get(sig, [])
            if not entries:
                continue
            frac = len(entries) / (n_pages / 2)
            if frac >= t.running_head_min_frac:
                ys = [y for _, y in entries]
                if max(ys) - min(ys) <= t.running_head_y_tolerance_frac * 2:
                    return True
        return False

    drop_sigs = {sig for sig in {*odd_sig, *even_sig} if qualifies(sig)}

    def is_page_number_like(text: str) -> bool:
        stripped = text.strip()
        return bool(
            _DIGITS_ONLY_RE.match(stripped)
            or _PAGE_NUM_RE.match(stripped)
            or (_ROMAN_RE.match(stripped) and stripped != "")
        )

    result: list[tuple[PageRaw, tuple[Block, ...]]] = []
    for page_idx, (page, blocks) in enumerate(pages):
        infos = page_line_info[page_idx]
        band_block_ids = {id(b) for b, _, _ in infos}
        new_blocks = []
        for block in blocks:
            if id(block) in band_block_ids:
                sig = _normalise(block.text)
                if sig in drop_sigs or is_page_number_like(block.text):
                    continue
            new_blocks.append(block)
        result.append((page, tuple(new_blocks)))
    return tuple(result)


def _ends_with_hyphen(text: str) -> tuple[bool, str]:
    if text and text[-1] in _HYPHENS:
        return True, text[:-1]
    return False, text


def _join_lines(tail: str, head: str) -> str:
    is_hyphen, tail_wo_hyphen = _ends_with_hyphen(tail)
    if is_hyphen and head[:1].islower():
        char_before = tail_wo_hyphen[-1:] if tail_wo_hyphen else ""
        if char_before.isupper() or char_before.isdigit():
            return tail + head
        return tail_wo_hyphen + head
    return f"{tail} {head}"


def join_document(pages: Sequence[tuple[PageRaw, tuple[Block, ...]]]) -> tuple[Block, ...]:
    """Join per-page blocks into a flat document, merging hyphenation and cross-page paragraphs."""
    flat: list[Block] = []
    for _, blocks in pages:
        flat.extend(blocks)

    merged: list[Block] = []
    for block in flat:
        if not merged:
            merged.append(block)
            continue
        prev = merged[-1]
        can_merge = (
            prev.kind == "paragraph"
            and block.kind == "paragraph"
            and prev.text
            and prev.text.rstrip()[-1:] not in _TERMINAL_PUNCT
            and (block.text[:1].islower() or (prev.text and prev.text[-1:] in _HYPHENS))
            and prev.font_key is not None
            and prev.font_key == block.font_key
        )
        if can_merge:
            joined_text = _join_lines(prev.text, block.text)
            source_pages = tuple(dict.fromkeys((*prev.pages, *block.pages)))
            new_bbox = (
                min(prev.bbox[0], block.bbox[0]),
                min(prev.bbox[1], block.bbox[1]),
                max(prev.bbox[2], block.bbox[2]),
                max(prev.bbox[3], block.bbox[3]),
            )
            merged[-1] = Block(
                kind="paragraph",
                text=joined_text,
                pages=source_pages,
                bbox=new_bbox,
                font_key=prev.font_key,
                level=prev.level,
            )
        else:
            merged.append(block)

    return tuple(merged)
