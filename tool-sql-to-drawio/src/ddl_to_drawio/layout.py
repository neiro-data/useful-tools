"""Deterministic grid layout for table boxes.

Sizes each box from its column count and places boxes in a grid with generous
spacing so nothing overlaps when the file is first opened. Users can still run
draw.io's Arrange -> Layout -> Organic afterwards for a nicer arrangement.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ddl_to_drawio.model import Schema, TableId

TABLE_WIDTH = 220
ROW_HEIGHT = 30
HEADER_HEIGHT = 30
HORIZONTAL_GAP = 80
VERTICAL_GAP = 80


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

    row_heights: dict[int, int] = {}
    for index, table_id in enumerate(ordered_ids):
        row = index // columns_per_row
        table = schema.tables[table_id]
        height = HEADER_HEIGHT + ROW_HEIGHT * max(1, len(table.columns))
        row_heights[row] = max(row_heights.get(row, 0), height)

    y_offsets: dict[int, int] = {}
    running_y = 0
    for row in sorted(row_heights):
        y_offsets[row] = running_y
        running_y += row_heights[row] + VERTICAL_GAP

    for index, table_id in enumerate(ordered_ids):
        row = index // columns_per_row
        col = index % columns_per_row
        table = schema.tables[table_id]
        height = HEADER_HEIGHT + ROW_HEIGHT * max(1, len(table.columns))
        x = col * (TABLE_WIDTH + HORIZONTAL_GAP)
        y = y_offsets[row]
        positions[table_id] = BoxPosition(x=x, y=y, width=TABLE_WIDTH, height=height)

    return positions
