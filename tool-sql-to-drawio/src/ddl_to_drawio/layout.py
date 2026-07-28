"""Deterministic grid layout for table boxes.

Sizes each box from its column count and places boxes in a grid with generous
spacing so nothing overlaps when the file is first opened. Users can still run
draw.io's Arrange -> Layout -> Organic afterwards for a nicer arrangement.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ddl_to_drawio.model import Schema, Table, TableId

MIN_TABLE_WIDTH = 220
MAX_TABLE_WIDTH = 460
PIXELS_PER_CHAR = 7
LABEL_PADDING = 24
ROW_HEIGHT = 30
HEADER_HEIGHT = 30
HORIZONTAL_GAP = 80
VERTICAL_GAP = 80

# Shared with emitter._column_label -- the single source of truth for these prefixes.
PK_PREFIX = "PK "
FK_PREFIX = "FK "

# Bold header text renders wider per character than the regular column labels.
_HEADER_WEIGHT = 1.15


def _longest_label_length(table: Table, fk_source_columns: set[tuple[TableId, str]]) -> int:
    """Return the character length of the table's longest rendered column label."""
    lengths = [0]
    for column in table.columns:
        is_fk = (table.table_id, column.name) in fk_source_columns
        prefix_len = (len(PK_PREFIX) if column.is_primary_key else 0) + (
            len(FK_PREFIX) if is_fk else 0
        )
        label_len = prefix_len + len(column.name)
        if column.type_text:
            label_len += len(column.type_text) + 2
        lengths.append(label_len)
    return max(lengths)


def _table_width(table: Table, fk_source_columns: set[tuple[TableId, str]]) -> int:
    """Compute a table's box width from its longest column label, clamped."""
    column_chars = _longest_label_length(table, fk_source_columns)
    header_chars = len(str(table.table_id)) * _HEADER_WEIGHT
    chars = max(column_chars, header_chars)
    width = round(chars * PIXELS_PER_CHAR + LABEL_PADDING)
    return max(MIN_TABLE_WIDTH, min(MAX_TABLE_WIDTH, width))


@dataclass(frozen=True, slots=True)
class BoxPosition:
    """Top-left position and size of a table box."""

    x: int
    y: int
    width: int
    height: int


def compute_layout(schema: Schema) -> dict[TableId, BoxPosition]:
    """Place each table in a deterministic grid, ordered by table identity."""
    ordered_ids = sorted(schema.tables, key=lambda t: (t.schema, t.name))
    if not ordered_ids:
        return {}

    columns_per_row = max(1, math.ceil(math.sqrt(len(ordered_ids))))
    positions: dict[TableId, BoxPosition] = {}

    fk_source_columns = {(fk.source_table, fk.source_column) for fk in schema.foreign_keys}
    widths = {
        table_id: _table_width(schema.tables[table_id], fk_source_columns)
        for table_id in ordered_ids
    }

    row_heights: dict[int, int] = {}
    grid_column_widths: dict[int, int] = {}
    for index, table_id in enumerate(ordered_ids):
        row = index // columns_per_row
        col = index % columns_per_row
        table = schema.tables[table_id]
        height = HEADER_HEIGHT + ROW_HEIGHT * max(1, len(table.columns))
        row_heights[row] = max(row_heights.get(row, 0), height)
        grid_column_widths[col] = max(grid_column_widths.get(col, 0), widths[table_id])

    y_offsets: dict[int, int] = {}
    running_y = 0
    for row in sorted(row_heights):
        y_offsets[row] = running_y
        running_y += row_heights[row] + VERTICAL_GAP

    x_offsets: dict[int, int] = {}
    running_x = 0
    for col in sorted(grid_column_widths):
        x_offsets[col] = running_x
        running_x += grid_column_widths[col] + HORIZONTAL_GAP

    for index, table_id in enumerate(ordered_ids):
        row = index // columns_per_row
        col = index % columns_per_row
        table = schema.tables[table_id]
        height = HEADER_HEIGHT + ROW_HEIGHT * max(1, len(table.columns))
        x = x_offsets[col]
        y = y_offsets[row]
        positions[table_id] = BoxPosition(x=x, y=y, width=widths[table_id], height=height)

    return positions
