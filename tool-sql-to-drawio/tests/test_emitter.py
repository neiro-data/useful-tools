"""Tests for ddl_to_drawio.emitter."""

from pathlib import Path
from xml.etree import ElementTree

from ddl_to_drawio.emitter import _column_cell_id, _column_name_label, build_mxgraph_xml
from ddl_to_drawio.layout import (
    MAX_TABLE_WIDTH,
    MIN_TABLE_WIDTH,
    MIN_TYPE_WIDTH,
    _table_widths,
    compute_layout,
)
from ddl_to_drawio.model import Column, ForeignKey, Schema, Table, TableId
from ddl_to_drawio.parser import parse_ddl

FIXTURE = Path(__file__).parent / "fixtures" / "sample_plants.sql"


def _fixture_schema() -> Schema:
    return parse_ddl(FIXTURE.read_text(encoding="utf-8"))


def test_emitted_xml_is_well_formed_and_parseable() -> None:
    # Arrange
    schema = _fixture_schema()

    # Act
    xml_text = build_mxgraph_xml(schema)
    tree = ElementTree.fromstring(xml_text)  # noqa: S314 -- trusted, self-generated XML

    # Assert
    assert tree.tag == "mxfile"


def test_emitted_xml_has_four_table_vertices_and_three_edges() -> None:
    # Arrange
    schema = _fixture_schema()

    # Act
    xml_text = build_mxgraph_xml(schema)
    tree = ElementTree.fromstring(xml_text)  # noqa: S314 -- trusted, self-generated XML
    cells = tree.findall(".//mxCell")

    # Assert
    table_vertices = [
        c for c in cells if c.get("vertex") == "1" and "shape=table;" in (c.get("style") or "")
    ]
    edges = [c for c in cells if c.get("edge") == "1"]
    assert len(table_vertices) == 4
    assert len(edges) == 3


def test_every_edge_endpoint_resolves_to_a_column_row_cell() -> None:
    # Arrange
    schema = _fixture_schema()

    # Act
    xml_text = build_mxgraph_xml(schema)
    tree = ElementTree.fromstring(xml_text)  # noqa: S314 -- trusted, self-generated XML
    cells = tree.findall(".//mxCell")
    row_cell_ids = {
        c.get("id")
        for c in cells
        if c.get("vertex") == "1" and "shape=tableRow" in (c.get("style") or "")
    }
    edges = [c for c in cells if c.get("edge") == "1"]

    # Assert
    assert len(edges) == 3
    for edge in edges:
        assert edge.get("source") in row_cell_ids
        assert edge.get("target") in row_cell_ids


def test_output_is_byte_identical_across_two_runs() -> None:
    # Arrange
    schema = _fixture_schema()

    # Act
    first = build_mxgraph_xml(schema)
    second = build_mxgraph_xml(schema)

    # Assert
    assert first == second


def test_punctuation_only_differences_produce_distinct_stable_cell_ids() -> None:
    # Arrange
    sql = 'CREATE TABLE "my-table" (id INT); CREATE TABLE "my_table" (id INT);'
    schema = parse_ddl(sql)

    # Act
    first = build_mxgraph_xml(schema)
    second = build_mxgraph_xml(schema)
    tree = ElementTree.fromstring(first)  # noqa: S314 -- trusted, self-generated XML
    table_cell_ids = [
        c.get("id")
        for c in tree.findall(".//mxCell")
        if c.get("vertex") == "1" and "shape=table;" in (c.get("style") or "")
    ]

    # Assert: distinct ids, no collision, and byte-identical across runs
    assert len(table_cell_ids) == 2
    assert len(set(table_cell_ids)) == 2
    assert first == second


def test_table_row_cells_have_empty_value_and_name_type_children() -> None:
    # Arrange
    schema = _fixture_schema()

    # Act
    xml_text = build_mxgraph_xml(schema)
    tree = ElementTree.fromstring(xml_text)  # noqa: S314 -- trusted, self-generated XML
    cells = tree.findall(".//mxCell")
    row_cells = [
        c for c in cells if c.get("vertex") == "1" and "shape=tableRow" in (c.get("style") or "")
    ]
    part_cells = {
        c.get("id"): c
        for c in cells
        if c.get("vertex") == "1" and "shape=partialRectangle" in (c.get("style") or "")
    }

    # Assert
    assert row_cells, "expected at least one tableRow cell"
    for row_cell in row_cells:
        row_id = row_cell.get("id")
        assert row_cell.get("value") == ""

        name_cell = part_cells.get(f"{row_id}-name")
        type_cell = part_cells.get(f"{row_id}-type")
        assert name_cell is not None, f"missing name part for row {row_id}"
        assert type_cell is not None, f"missing type part for row {row_id}"
        assert name_cell.get("parent") == row_id
        assert type_cell.get("parent") == row_id
        assert name_cell.get("value")

        for part_cell in (name_cell, type_cell):
            part_geometry = part_cell.find("mxGeometry")
            assert part_geometry is not None
            alternate_bounds = part_geometry.find("mxRectangle")
            assert alternate_bounds is not None
            assert alternate_bounds.get("as") == "alternateBounds"
            assert alternate_bounds.get("width") == part_geometry.get("width")
            assert alternate_bounds.get("height") == part_geometry.get("height")


def test_name_part_is_bold_and_type_part_is_not() -> None:
    # Arrange
    schema = _fixture_schema()

    # Act
    xml_text = build_mxgraph_xml(schema)
    tree = ElementTree.fromstring(xml_text)  # noqa: S314 -- trusted, self-generated XML
    cells = tree.findall(".//mxCell")

    # Assert
    name_cells = [c for c in cells if (c.get("id") or "").endswith("-name")]
    type_cells = [c for c in cells if (c.get("id") or "").endswith("-type")]
    assert name_cells and type_cells
    for cell in name_cells:
        assert "fontStyle=1" in (cell.get("style") or "")
    for cell in type_cells:
        assert "fontStyle=1" not in (cell.get("style") or "")


def test_table_header_is_grey_and_rows_are_white() -> None:
    # Arrange
    schema = _fixture_schema()

    # Act
    xml_text = build_mxgraph_xml(schema)
    tree = ElementTree.fromstring(xml_text)  # noqa: S314 -- trusted, self-generated XML
    cells = tree.findall(".//mxCell")

    # Assert
    table_cells = [c for c in cells if (c.get("style") or "").startswith("shape=table;")]
    row_cells = [
        c for c in cells if c.get("vertex") == "1" and "shape=tableRow" in (c.get("style") or "")
    ]
    assert table_cells
    for cell in table_cells:
        assert "fillColor=#B8B8B8" in (cell.get("style") or "")
    assert row_cells
    for cell in row_cells:
        assert "fillColor=#FFFFFF" in (cell.get("style") or "")


def test_type_column_is_aligned_within_each_table() -> None:
    # Arrange
    schema = _fixture_schema()

    # Act
    xml_text = build_mxgraph_xml(schema)
    tree = ElementTree.fromstring(xml_text)  # noqa: S314 -- trusted, self-generated XML
    cells = tree.findall(".//mxCell")
    table_cells = {
        c.get("id"): c for c in cells if (c.get("style") or "").startswith("shape=table;")
    }
    row_cells = [
        c for c in cells if c.get("vertex") == "1" and "shape=tableRow" in (c.get("style") or "")
    ]
    part_cells = {
        c.get("id"): c
        for c in cells
        if c.get("vertex") == "1" and "shape=partialRectangle" in (c.get("style") or "")
    }

    # Assert
    rows_by_table: dict[str, list[ElementTree.Element]] = {}
    for row_cell in row_cells:
        parent = row_cell.get("parent")
        assert parent is not None
        rows_by_table.setdefault(parent, []).append(row_cell)

    for table_id, rows in rows_by_table.items():
        table_geometry = table_cells[table_id].find("mxGeometry")
        assert table_geometry is not None
        box_width = float(table_geometry.get("width", 0))

        name_widths = set()
        for row_cell in rows:
            row_id = row_cell.get("id")
            name_cell = part_cells[f"{row_id}-name"]
            type_cell = part_cells[f"{row_id}-type"]
            name_geometry = name_cell.find("mxGeometry")
            type_geometry = type_cell.find("mxGeometry")
            assert name_geometry is not None
            assert type_geometry is not None

            name_x = float(name_geometry.get("x", 0))
            name_width = float(name_geometry.get("width", 0))
            type_x = float(type_geometry.get("x", 0))
            type_width = float(type_geometry.get("width", 0))

            name_widths.add(name_width)
            assert name_x + name_width == type_x
            assert name_width + type_width == box_width

            type_text = type_cell.get("value") or ""
            assert ":" not in type_text
            if type_text:
                assert (name_cell.get("value") or "").endswith(":")

        assert len(name_widths) == 1, f"name widths differ within table {table_id}"


def test_row_cells_carry_edge_anchor_ports() -> None:
    # Arrange
    schema = _fixture_schema()

    # Act
    xml_text = build_mxgraph_xml(schema)
    tree = ElementTree.fromstring(xml_text)  # noqa: S314 -- trusted, self-generated XML
    row_cells = [
        c
        for c in tree.findall(".//mxCell")
        if c.get("vertex") == "1" and "shape=tableRow" in (c.get("style") or "")
    ]

    # Assert
    assert row_cells, "expected at least one tableRow cell"
    for row_cell in row_cells:
        style = row_cell.get("style") or ""
        assert "points=[[0,0.5],[1,0.5]]" in style
        assert "portConstraint=eastwest" in style


def test_all_cell_ids_are_unique_and_parents_resolve() -> None:
    # Arrange
    schema = _fixture_schema()

    # Act
    xml_text = build_mxgraph_xml(schema)
    tree = ElementTree.fromstring(xml_text)  # noqa: S314 -- trusted, self-generated XML
    cells = tree.findall(".//mxCell")
    ids = [c.get("id") for c in cells if c.get("id")]

    # Assert
    assert len(ids) == len(set(ids)), "duplicate mxCell ids found"
    id_set = set(ids)
    for cell in cells:
        parent = cell.get("parent")
        if parent:
            assert parent in id_set, f"orphan parent reference: {cell.get('id')} -> {parent}"


def test_table_bounding_boxes_do_not_overlap() -> None:
    # Arrange
    schema = _fixture_schema()

    # Act
    xml_text = build_mxgraph_xml(schema)
    tree = ElementTree.fromstring(xml_text)  # noqa: S314 -- trusted, self-generated XML
    tables = [
        c for c in tree.findall(".//mxCell") if (c.get("style") or "").startswith("shape=table;")
    ]

    def box(cell: ElementTree.Element) -> tuple[float, float, float, float]:
        geometry = cell.find("mxGeometry")
        assert geometry is not None
        return (
            float(geometry.get("x", 0)),
            float(geometry.get("y", 0)),
            float(geometry.get("width", 0)),
            float(geometry.get("height", 0)),
        )

    def overlaps(
        a: tuple[float, float, float, float], b: tuple[float, float, float, float]
    ) -> bool:
        ax, ay, aw, ah = a
        bx, by, bw, bh = b
        return not (ax + aw <= bx or bx + bw <= ax or ay + ah <= by or by + bh <= ay)

    # Assert
    boxes = [box(t) for t in tables]
    assert len(boxes) == 4
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            assert not overlaps(boxes[i], boxes[j]), (
                f"tables {tables[i].get('id')} and {tables[j].get('id')} overlap"
            )


def _schema_with_single_table(table_id: TableId, columns: list[Column]) -> Schema:
    return Schema(tables={table_id: Table(table_id=table_id, columns=columns)})


def test_short_column_table_width_clamps_to_minimum() -> None:
    # Arrange
    table_id = TableId(schema="public", name="t")
    schema = _schema_with_single_table(table_id, [Column(name="id", type_text="int")])

    # Act
    positions = compute_layout(schema)

    # Assert
    assert positions[table_id].width == MIN_TABLE_WIDTH


def test_long_column_label_widens_the_table() -> None:
    # Arrange
    table_id = TableId(schema="public", name="t")
    schema = _schema_with_single_table(
        table_id,
        [Column(name="a_moderately_long_column_name", type_text="varchar(255)")],
    )

    # Act
    positions = compute_layout(schema)

    # Assert
    assert MIN_TABLE_WIDTH < positions[table_id].width < MAX_TABLE_WIDTH


def test_absurdly_long_column_label_clamps_to_maximum() -> None:
    # Arrange
    table_id = TableId(schema="public", name="t")
    schema = _schema_with_single_table(
        table_id,
        [Column(name="x" * 200, type_text="varchar(255)")],
    )

    # Act
    positions = compute_layout(schema)

    # Assert
    assert positions[table_id].width == MAX_TABLE_WIDTH
    assert positions[table_id].name_width < positions[table_id].width
    assert positions[table_id].name_width <= MAX_TABLE_WIDTH - MIN_TYPE_WIDTH


def test_long_table_name_with_short_columns_widens_the_table() -> None:
    # Arrange
    table_id = TableId(schema="analytics_staging", name="customer_order_line_items")
    schema = _schema_with_single_table(table_id, [Column(name="id", type_text="int")])

    # Act
    positions = compute_layout(schema)

    # Assert
    assert positions[table_id].width > MIN_TABLE_WIDTH


def test_layout_widths_are_deterministic_across_calls() -> None:
    # Arrange
    schema = _fixture_schema()

    # Act
    first = compute_layout(schema)
    second = compute_layout(schema)

    # Assert
    assert {tid: pos.width for tid, pos in first.items()} == {
        tid: pos.width for tid, pos in second.items()
    }


def test_special_characters_are_xml_escaped() -> None:
    # Arrange
    sql = 'CREATE TABLE "weird&name" (id SERIAL PRIMARY KEY, "col<>" TEXT NOT NULL);'
    schema = parse_ddl(sql)

    # Act
    xml_text = build_mxgraph_xml(schema)

    # Assert: parses cleanly despite raw & < > in identifiers
    ElementTree.fromstring(xml_text)  # noqa: S314 -- trusted, self-generated XML
    assert "&amp;" in xml_text


def test_zero_column_table_does_not_crash_and_has_no_row_cells() -> None:
    # Arrange
    table_id = TableId(schema="public", name="empty")
    schema = _schema_with_single_table(table_id, [])

    # Act
    positions = compute_layout(schema)
    xml_text = build_mxgraph_xml(schema)
    tree = ElementTree.fromstring(xml_text)  # noqa: S314 -- trusted, self-generated XML

    # Assert: still gets a valid box, but zero row/part cells
    assert positions[table_id].width >= MIN_TABLE_WIDTH
    assert positions[table_id].name_width < positions[table_id].width
    row_cells = [
        c
        for c in tree.findall(".//mxCell")
        if c.get("vertex") == "1" and "shape=tableRow" in (c.get("style") or "")
    ]
    part_cells = [
        c
        for c in tree.findall(".//mxCell")
        if c.get("vertex") == "1" and "shape=partialRectangle" in (c.get("style") or "")
    ]
    assert row_cells == []
    assert part_cells == []


def test_column_with_empty_type_text_omits_colon_and_keeps_positive_widths() -> None:
    # Arrange
    table_id = TableId(schema="public", name="t")
    schema = _schema_with_single_table(table_id, [Column(name="notes", type_text="")])

    # Act
    positions = compute_layout(schema)
    xml_text = build_mxgraph_xml(schema)
    tree = ElementTree.fromstring(xml_text)  # noqa: S314 -- trusted, self-generated XML

    # Assert
    position = positions[table_id]
    assert position.name_width > 0
    assert position.width - position.name_width >= MIN_TYPE_WIDTH
    name_cell = next(c for c in tree.findall(".//mxCell") if (c.get("id") or "").endswith("-name"))
    type_cell = next(c for c in tree.findall(".//mxCell") if (c.get("id") or "").endswith("-type"))
    assert name_cell.get("value") == "notes"
    assert type_cell.get("value") == ""


def test_name_width_invariants_hold_for_extreme_inputs() -> None:
    # Arrange: exhaustively probe clamp math for name-only, type-only, and both extreme lengths.
    cases = [
        [Column(name="x" * 500, type_text="")],
        [Column(name="", type_text="x" * 500)],
        [Column(name="x" * 500, type_text="y" * 500)],
        [Column(name="a", type_text="b")],
        [],
    ]

    for columns in cases:
        table_id = TableId(schema="public", name="probe")
        schema = _schema_with_single_table(table_id, columns)

        # Act
        name_width, total_width = _table_widths(schema.tables[table_id], fk_source_columns=set())

        # Assert
        assert MIN_TABLE_WIDTH <= total_width <= MAX_TABLE_WIDTH
        assert 0 < name_width < total_width
        assert total_width - name_width >= MIN_TYPE_WIDTH


def test_narrow_table_sharing_grid_column_with_wide_table_keeps_own_split() -> None:
    # Arrange: two tables landing in the same grid column (index 0 and 1, columns_per_row=2
    # for a 3-table schema puts table 0 above table 2 in column 0) with very different widths.
    narrow_id = TableId(schema="public", name="a_narrow")
    wide_id = TableId(schema="public", name="c_wide")
    filler_id = TableId(schema="public", name="b_filler")
    schema = Schema(
        tables={
            narrow_id: Table(table_id=narrow_id, columns=[Column(name="id", type_text="int")]),
            filler_id: Table(table_id=filler_id, columns=[Column(name="id", type_text="int")]),
            wide_id: Table(
                table_id=wide_id,
                columns=[
                    Column(
                        name="a_very_long_descriptive_column_name_indeed",
                        type_text="varchar(500)",
                    )
                ],
            ),
        }
    )

    # Act
    positions = compute_layout(schema)
    xml_text = build_mxgraph_xml(schema)
    tree = ElementTree.fromstring(xml_text)  # noqa: S314 -- trusted, self-generated XML

    # Assert: narrow table keeps its own (smaller) box width, not stretched to match wide table.
    assert positions[narrow_id].width < positions[wide_id].width
    for table_id in (narrow_id, wide_id):
        position = positions[table_id]
        assert position.name_width > 0
        assert position.width - position.name_width >= MIN_TYPE_WIDTH

    part_cells = {
        c.get("id"): c
        for c in tree.findall(".//mxCell")
        if c.get("vertex") == "1" and "shape=partialRectangle" in (c.get("style") or "")
    }
    for table_id, column_name in (
        (narrow_id, "id"),
        (wide_id, "a_very_long_descriptive_column_name_indeed"),
    ):
        row_id = _column_cell_id(table_id, column_name)
        name_cell = part_cells.get(f"{row_id}-name")
        type_cell = part_cells.get(f"{row_id}-type")
        assert name_cell is not None
        assert type_cell is not None
        name_geometry = name_cell.find("mxGeometry")
        type_geometry = type_cell.find("mxGeometry")
        assert name_geometry is not None and type_geometry is not None
        assert float(type_geometry.get("width", 0)) > 0
        assert float(name_geometry.get("x", 0)) + float(name_geometry.get("width", 0)) == float(
            type_geometry.get("x", 0)
        )


def test_pk_fk_combined_prefix_width_matches_emitter_label_length() -> None:
    # Arrange: layout._table_widths duplicates the label math in emitter._column_name_label;
    # verify they compute the same character count for a column that is both PK and FK.
    table_id = TableId(schema="public", name="link")
    source_table_id = TableId(schema="public", name="other")
    column = Column(name="id", type_text="int", is_primary_key=True)
    schema = Schema(
        tables={table_id: Table(table_id=table_id, columns=[column])},
        foreign_keys=[
            ForeignKey(
                source_table=table_id,
                source_column="id",
                target_table=source_table_id,
                target_column="id",
            )
        ],
    )
    fk_source_columns = {(fk.source_table, fk.source_column) for fk in schema.foreign_keys}

    # Act
    name_width, _ = _table_widths(schema.tables[table_id], fk_source_columns)
    label = _column_name_label(column.name, is_pk=True, is_fk=True, has_type=True)

    # Assert: label text is exactly "PK FK id:" and layout's char-count math agrees.
    assert label == "PK FK id:"
    from ddl_to_drawio.layout import NAME_PADDING, PIXELS_PER_CHAR

    expected_width = round(len(label) * PIXELS_PER_CHAR) + NAME_PADDING
    # This table is tiny and well under MAX_TABLE_WIDTH, so clamping does not apply
    # here: name_width must equal the unclamped expectation exactly.
    assert name_width == expected_width
