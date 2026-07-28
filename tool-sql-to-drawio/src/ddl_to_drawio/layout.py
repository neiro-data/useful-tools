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
# A row's total horizontal padding is NAME_PADDING + TYPE_PADDING (32px), replacing the
# old single 24px LABEL_PADDING, so tables are ~8px wider from padding alone.
NAME_PADDING = 16
TYPE_PADDING = 16
MIN_TYPE_WIDTH = 60
ROW_HEIGHT = 30
HEADER_HEIGHT = 30
HORIZONTAL_GAP = 80
VERTICAL_GAP = 80

# Shared with emitter._column_name_label -- the single source of truth for these prefixes.
# _table_widths below re-derives the same label-length math and must be kept in sync with it.
PK_PREFIX = "PK "
FK_PREFIX = "FK "

# Bold header text renders wider per character than the regular column labels.
_HEADER_WEIGHT = 1.15


def _table_widths(table: Table, fk_source_columns: set[tuple[TableId, str]]) -> tuple[int, int]:
    """Compute a table's (name_width, total_width), clamped.

    ``name_width`` sizes the name/prefix sub-column; ``total_width`` sizes the
    full table box (name sub-column + type sub-column).
    """
    name_chars = 0
    type_chars = 0
    for column in table.columns:
        is_fk = (table.table_id, column.name) in fk_source_columns
        prefix_len = (len(PK_PREFIX) if column.is_primary_key else 0) + (
            len(FK_PREFIX) if is_fk else 0
        )
        name_len = prefix_len + len(column.name) + (1 if column.type_text else 0)
        name_chars = max(name_chars, name_len)
        type_chars = max(type_chars, len(column.type_text))

    name_width = round(name_chars * PIXELS_PER_CHAR) + NAME_PADDING
    type_width = round(type_chars * PIXELS_PER_CHAR) + TYPE_PADDING
    header_width = round(len(str(table.table_id)) * _HEADER_WEIGHT * PIXELS_PER_CHAR) + NAME_PADDING

    total = max(name_width + type_width, header_width, MIN_TABLE_WIDTH)
    total = max(MIN_TABLE_WIDTH, min(MAX_TABLE_WIDTH, total))

    name_width = max(1, min(name_width, total - MIN_TYPE_WIDTH))
    return name_width, total


@dataclass(frozen=True, slots=True)
class BoxPosition:
    """Top-left position and size of a table box."""

    x: int
    y: int
    width: int
    height: int
    name_width: int


def compute_layout(schema: Schema) -> dict[TableId, BoxPosition]:
    """Place each table in a deterministic grid, ordered by table identity."""
    ordered_ids = sorted(schema.tables, key=lambda t: (t.schema, t.name))
    if not ordered_ids:
        return {}

    columns_per_row = max(1, math.ceil(math.sqrt(len(ordered_ids))))
    positions: dict[TableId, BoxPosition] = {}

    fk_source_columns = {(fk.source_table, fk.source_column) for fk in schema.foreign_keys}
    name_widths: dict[TableId, int] = {}
    widths: dict[TableId, int] = {}
    for table_id in ordered_ids:
        name_width, total_width = _table_widths(schema.tables[table_id], fk_source_columns)
        name_widths[table_id] = name_width
        widths[table_id] = total_width

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
        positions[table_id] = BoxPosition(
            x=x, y=y, width=widths[table_id], height=height, name_width=name_widths[table_id]
        )

    return positions
