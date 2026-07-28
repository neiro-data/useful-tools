"""Tests for ddl_to_drawio.emitter."""

from pathlib import Path
from xml.etree import ElementTree

from ddl_to_drawio.emitter import build_mxgraph_xml
from ddl_to_drawio.model import Schema
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


def test_special_characters_are_xml_escaped() -> None:
    # Arrange
    sql = 'CREATE TABLE "weird&name" (id SERIAL PRIMARY KEY, "col<>" TEXT NOT NULL);'
    schema = parse_ddl(sql)

    # Act
    xml_text = build_mxgraph_xml(schema)

    # Assert: parses cleanly despite raw & < > in identifiers
    ElementTree.fromstring(xml_text)  # noqa: S314 -- trusted, self-generated XML
    assert "&amp;" in xml_text
