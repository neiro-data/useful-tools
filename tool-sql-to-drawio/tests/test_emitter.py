"""Tests for ddl_to_drawio.emitter."""

from pathlib import Path
from xml.etree import ElementTree

from ddl_to_drawio.emitter import build_mxgraph_xml
from ddl_to_drawio.layout import MAX_TABLE_WIDTH, MIN_TABLE_WIDTH, compute_layout
from ddl_to_drawio.model import Column, Schema, Table, TableId
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


def test_table_row_cells_have_empty_value_and_a_label_child() -> None:
    # Arrange
    schema = _fixture_schema()

    # Act
    xml_text = build_mxgraph_xml(schema)
    tree = ElementTree.fromstring(xml_text)  # noqa: S314 -- trusted, self-generated XML
    cells = tree.findall(".//mxCell")
    row_cells = [
        c for c in cells if c.get("vertex") == "1" and "shape=tableRow" in (c.get("style") or "")
    ]
    label_cells = {
        c.get("id"): c
        for c in cells
        if c.get("vertex") == "1" and "shape=partialRectangle" in (c.get("style") or "")
    }

    # Assert
    assert row_cells, "expected at least one tableRow cell"
    for row_cell in row_cells:
        row_id = row_cell.get("id")
        assert row_cell.get("value") == ""

        label_cell = label_cells.get(f"{row_id}-label")
        assert label_cell is not None, f"missing label child for row {row_id}"
        assert label_cell.get("parent") == row_id
        assert label_cell.get("value")

        row_geometry = row_cell.find("mxGeometry")
        assert row_geometry is not None
        label_geometry = label_cell.find("mxGeometry")
        assert label_geometry is not None
        assert label_geometry.get("width") == row_geometry.get("width")
        assert label_geometry.get("height") == row_geometry.get("height")

        alternate_bounds = label_geometry.find("mxRectangle")
        assert alternate_bounds is not None
        assert alternate_bounds.get("as") == "alternateBounds"
        assert alternate_bounds.get("width") == label_geometry.get("width")
        assert alternate_bounds.get("height") == label_geometry.get("height")


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
