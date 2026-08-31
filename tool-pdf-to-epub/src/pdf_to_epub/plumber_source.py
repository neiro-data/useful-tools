"""Table extraction via pdfplumber. Sole importer of ``pdfplumber`` in this library."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import pdfplumber


@dataclass(frozen=True)
class RawTable:
    bbox: tuple[float, float, float, float]
    rows: tuple[tuple[str, ...], ...]


def _tables_for_page(page: pdfplumber.page.Page) -> tuple[RawTable, ...]:
    tables = page.find_tables()
    result = []
    for table in tables:
        rows = tuple(tuple((cell or "").strip() for cell in row) for row in table.extract())
        x0, top, x1, bottom = table.bbox
        bbox = (float(x0), float(top), float(x1), float(bottom))
        result.append(RawTable(bbox=bbox, rows=rows))
    return tuple(result)


def extract_tables(path: Path, page_number: int) -> tuple[RawTable, ...]:
    """Extract raw table grids from a single (1-based) page of ``path``."""
    with pdfplumber.open(path) as pdf:
        return _tables_for_page(pdf.pages[page_number - 1])


def extract_tables_for_pages(
    path: Path, page_numbers: Sequence[int]
) -> Mapping[int, tuple[RawTable, ...]]:
    """Extract raw table grids for many (1-based) pages of ``path`` in a single open/parse."""
    result: dict[int, tuple[RawTable, ...]] = {}
    if not page_numbers:
        return result
    with pdfplumber.open(path) as pdf:
        for page_number in page_numbers:
            tables = _tables_for_page(pdf.pages[page_number - 1])
            if tables:
                result[page_number] = tables
    return result
