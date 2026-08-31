"""Tests for high-confidence table to XHTML rendering."""

from __future__ import annotations

from pathlib import Path

from pdf_to_epub.config import Thresholds
from pdf_to_epub.plumber_source import RawTable, extract_tables
from pdf_to_epub.tables import table_to_xhtml
from tests.fixtures import make_pdfs

THRESHOLDS = Thresholds()


def test_clean_table_renders_with_correct_row_and_column_counts(tmp_path: Path) -> None:
    pdf_path = make_pdfs.make_table_page(tmp_path)
    raw_tables = extract_tables(pdf_path, 1)
    assert raw_tables

    xhtml = table_to_xhtml(raw_tables[0], THRESHOLDS)

    assert xhtml is not None
    assert xhtml.count("<tr>") == 4  # header row + 3 data rows
    assert xhtml.count("<th>") == 3
    assert xhtml.count("<td>") == 9


def test_ragged_table_returns_none() -> None:
    ragged = RawTable(
        bbox=(0.0, 0.0, 100.0, 100.0),
        rows=(
            ("Name", "Age", "City"),
            ("Alice", "30"),
            ("Bob", "25", "Chicago", "Extra"),
        ),
    )

    assert table_to_xhtml(ragged, THRESHOLDS) is None


def test_all_empty_row_returns_none() -> None:
    table = RawTable(
        bbox=(0.0, 0.0, 100.0, 100.0),
        rows=(
            ("Name", "Age"),
            ("", ""),
        ),
    )

    assert table_to_xhtml(table, THRESHOLDS) is None
