"""High-confidence table to XHTML rendering. Pure, stdlib-only."""

from __future__ import annotations

from pdf_to_epub.config import Thresholds
from pdf_to_epub.plumber_source import RawTable
from pdf_to_epub.xhtml import escape_text


def _looks_like_header(row: tuple[str, ...]) -> bool:
    return all(cell.strip() != "" for cell in row)


def table_to_xhtml(table: RawTable, t: Thresholds) -> str | None:
    """Render a table as semantic XHTML, or None if confidence is too low to trust it."""
    rows = table.rows
    if len(rows) < t.table_min_rows:
        return None

    col_count = len(rows[0])
    if col_count == 0:
        return None
    if any(len(row) != col_count for row in rows):
        return None
    if any(all(cell.strip() == "" for cell in row) for row in rows):
        return None

    header, *body = rows
    use_header = _looks_like_header(header)

    parts = ["<table>"]
    if use_header:
        parts.append("<thead><tr>")
        for cell in header:
            parts.append(f"<th>{escape_text(cell)}</th>")
        parts.append("</tr></thead>")
        data_rows: list[tuple[str, ...]] | tuple[tuple[str, ...], ...] = body
    else:
        data_rows = rows

    parts.append("<tbody>")
    for row in data_rows:
        parts.append("<tr>")
        for cell in row:
            parts.append(f"<td>{escape_text(cell)}</td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")

    return "".join(parts)
