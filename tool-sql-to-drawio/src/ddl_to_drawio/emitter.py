"""Emit a draw.io mxGraphModel XML document from the plain dataclass model.

Depends only on ddl_to_drawio.model dataclasses -- never on sqlglot AST types.
Column-level anchoring: each table row (one per column) is its own mxCell, and
foreign-key edges connect those column cells directly, not the parent table cells.
"""

from __future__ import annotations

import hashlib
import re
from xml.dom import minidom
from xml.etree.ElementTree import Element, SubElement, tostring

from ddl_to_drawio.layout import (
    FK_PREFIX,
    HEADER_HEIGHT,
    PK_PREFIX,
    ROW_HEIGHT,
    BoxPosition,
    compute_layout,
)
from ddl_to_drawio.model import Schema, TableId

_SLUG_RE = re.compile(r"[^a-zA-Z0-9_]+")
_HASH_LEN = 8


def _slug(text: str) -> str:
    """Collapse ``text`` to a deterministic, collision-free id fragment.

    Distinct identifiers that differ only in punctuation (e.g. ``"my-table"``
    vs ``"my_table"``) would otherwise collapse to the same slug. A short
    deterministic hash of the full input is appended so cell ids stay stable
    across runs while remaining unique per distinct identity.
    """
    collapsed = _SLUG_RE.sub("_", text)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:_HASH_LEN]
    return f"{collapsed}_{digest}"


def _table_cell_id(table_id: TableId) -> str:
    return f"table-{_slug(str(table_id))}"


def _column_cell_id(table_id: TableId, column_name: str) -> str:
    return f"col-{_slug(str(table_id))}-{_slug(column_name)}"


def _foreign_key_cell_id(
    source_table: TableId, source_column: str, target_table: TableId, target_column: str
) -> str:
    return (
        f"fk-{_slug(str(source_table))}-{_slug(source_column)}"
        f"__{_slug(str(target_table))}-{_slug(target_column)}"
    )


_PART_STYLE = (
    "shape=partialRectangle;connectable=0;fillColor=none;"
    "top=0;left=0;bottom=0;right=0;align=left;verticalAlign=middle;"
    "spacingLeft=6;spacingRight=6;overflow=hidden;whiteSpace=wrap;html=1;"
)


def _column_name_label(name: str, *, is_pk: bool, is_fk: bool, has_type: bool) -> str:
    prefix = ""
    if is_pk:
        prefix += PK_PREFIX
    if is_fk:
        prefix += FK_PREFIX
    label = f"{prefix}{name}"
    if has_type:
        label = f"{label}:"
    return label


def build_mxgraph_xml(schema: Schema) -> str:
    """Build the full <mxfile> draw.io document for the given schema.

    Deterministic: the same Schema always produces byte-identical XML.
    """
    positions = compute_layout(schema)
    fk_source_columns = {(fk.source_table, fk.source_column) for fk in schema.foreign_keys}

    mxfile = Element("mxfile", {"host": "app.diagrams.net"})
    diagram = SubElement(mxfile, "diagram", {"id": "ddl-to-drawio", "name": "ER Diagram"})
    model = SubElement(
        diagram,
        "mxGraphModel",
        {
            "dx": "800",
            "dy": "600",
            "grid": "1",
            "gridSize": "10",
            "guides": "1",
            "tooltips": "1",
            "connect": "1",
            "arrows": "1",
            "fold": "1",
            "page": "1",
            "pageScale": "1",
            "pageWidth": "850",
            "pageHeight": "1100",
            "math": "0",
            "shadow": "0",
        },
    )
    root = SubElement(model, "root")
    SubElement(root, "mxCell", {"id": "0"})
    SubElement(root, "mxCell", {"id": "1", "parent": "0"})

    ordered_ids = sorted(schema.tables, key=lambda t: (t.schema, t.name))

    for table_id in ordered_ids:
        table = schema.tables[table_id]
        position: BoxPosition = positions[table_id]
        table_cell_id = _table_cell_id(table_id)

        table_cell = SubElement(
            root,
            "mxCell",
            {
                "id": table_cell_id,
                "value": str(table_id),
                "style": (
                    "shape=table;startSize=30;container=1;collapsible=0;"
                    "childLayout=tableLayout;fixedRows=1;rowLines=0;fontStyle=1;"
                    "align=center;resizeLast=1;html=1;fillColor=#B8B8B8;"
                ),
                "vertex": "1",
                "parent": "1",
            },
        )
        SubElement(
            table_cell,
            "mxGeometry",
            {
                "x": str(position.x),
                "y": str(position.y),
                "width": str(position.width),
                "height": str(position.height),
                "as": "geometry",
            },
        )

        for index, column in enumerate(table.columns):
            column_cell_id = _column_cell_id(table_id, column.name)
            is_fk = (table_id, column.name) in fk_source_columns
            name_label = _column_name_label(
                column.name,
                is_pk=column.is_primary_key,
                is_fk=is_fk,
                has_type=bool(column.type_text),
            )
            row_cell = SubElement(
                root,
                "mxCell",
                {
                    "id": column_cell_id,
                    "value": "",
                    "style": (
                        "shape=tableRow;horizontal=0;startSize=0;swimlaneHead=0;"
                        "swimlaneBody=0;fillColor=#FFFFFF;collapsible=0;dropTarget=0;"
                        "points=[[0,0.5],[1,0.5]];portConstraint=eastwest;"
                        "top=0;left=0;right=0;bottom=1;html=1;"
                    ),
                    "vertex": "1",
                    "parent": table_cell_id,
                },
            )
            SubElement(
                row_cell,
                "mxGeometry",
                {
                    "y": str(HEADER_HEIGHT + index * ROW_HEIGHT),
                    "width": str(position.width),
                    "height": str(ROW_HEIGHT),
                    "as": "geometry",
                },
            )

            type_width = position.width - position.name_width

            name_cell = SubElement(
                root,
                "mxCell",
                {
                    "id": f"{column_cell_id}-name",
                    "value": name_label,
                    "style": f"{_PART_STYLE}fontStyle=1;",
                    "vertex": "1",
                    "parent": column_cell_id,
                },
            )
            name_geometry = SubElement(
                name_cell,
                "mxGeometry",
                {
                    "x": "0",
                    "width": str(position.name_width),
                    "height": str(ROW_HEIGHT),
                    "as": "geometry",
                },
            )
            SubElement(
                name_geometry,
                "mxRectangle",
                {
                    "width": str(position.name_width),
                    "height": str(ROW_HEIGHT),
                    "as": "alternateBounds",
                },
            )

            type_cell = SubElement(
                root,
                "mxCell",
                {
                    "id": f"{column_cell_id}-type",
                    "value": column.type_text,
                    "style": _PART_STYLE,
                    "vertex": "1",
                    "parent": column_cell_id,
                },
            )
            type_geometry = SubElement(
                type_cell,
                "mxGeometry",
                {
                    "x": str(position.name_width),
                    "width": str(type_width),
                    "height": str(ROW_HEIGHT),
                    "as": "geometry",
                },
            )
            SubElement(
                type_geometry,
                "mxRectangle",
                {
                    "width": str(type_width),
                    "height": str(ROW_HEIGHT),
                    "as": "alternateBounds",
                },
            )

    for fk in sorted(
        schema.foreign_keys,
        key=lambda f: (
            str(f.source_table),
            f.source_column,
            str(f.target_table),
            f.target_column,
        ),
    ):
        edge_id = _foreign_key_cell_id(
            fk.source_table, fk.source_column, fk.target_table, fk.target_column
        )
        source_cell_id = _column_cell_id(fk.source_table, fk.source_column)
        target_cell_id = _column_cell_id(fk.target_table, fk.target_column)
        edge_cell = SubElement(
            root,
            "mxCell",
            {
                "id": edge_id,
                "style": (
                    "edgeStyle=entityRelationEdgeStyle;html=1;endArrow=ERmany;"
                    "startArrow=ERone;rounded=0;"
                ),
                "edge": "1",
                "parent": "1",
                "source": source_cell_id,
                "target": target_cell_id,
            },
        )
        SubElement(edge_cell, "mxGeometry", {"relative": "1", "as": "geometry"})

    raw_bytes = tostring(mxfile, encoding="unicode")
    pretty = minidom.parseString(raw_bytes).toprettyxml(indent="  ")  # noqa: S318 -- trusted, self-generated XML
    lines = [line for line in pretty.splitlines() if line.strip()]
    return "\n".join(lines) + "\n"
