"""Tests for ddl_to_drawio.parser."""

from pathlib import Path

import pytest

from ddl_to_drawio.model import Schema, TableId
from ddl_to_drawio.parser import DdlParseError, parse_ddl

FIXTURE = Path(__file__).parent / "fixtures" / "sample_plants.sql"


def _load_fixture_schema() -> Schema:
    sql = FIXTURE.read_text(encoding="utf-8")
    return parse_ddl(sql)


def test_all_tables_parsed_with_correct_names() -> None:
    # Arrange / Act
    schema = _load_fixture_schema()

    # Assert
    expected = {
        TableId("public", "plants"),
        TableId("public", "plant_production"),
        TableId("public", "plant_maintenance"),
        TableId("public", "plant_emissions"),
    }
    assert set(schema.tables) == expected


def test_column_counts_and_types_and_nullability() -> None:
    # Arrange
    schema = _load_fixture_schema()

    # Act
    plants = schema.tables[TableId("public", "plants")]

    # Assert
    assert len(plants.columns) == 5
    by_name = {c.name: c for c in plants.columns}
    assert by_name["id"].is_primary_key is True
    assert by_name["name"].not_null is True
    assert "TEXT" in by_name["name"].type_text.upper()
    assert by_name["created_at"].not_null is False


def test_three_out_of_line_foreign_keys_resolved() -> None:
    # Arrange
    schema = _load_fixture_schema()

    # Act
    fk_pairs = {
        (str(fk.source_table), fk.source_column, str(fk.target_table), fk.target_column)
        for fk in schema.foreign_keys
    }

    # Assert
    assert fk_pairs == {
        ("public.plant_production", "plant_id", "public.plants", "id"),
        ("public.plant_maintenance", "plant_id", "public.plants", "id"),
        ("public.plant_emissions", "plant_id", "public.plants", "id"),
    }


def test_set_create_index_and_check_are_ignored() -> None:
    # Arrange / Act
    schema = _load_fixture_schema()

    # Assert: no spurious tables from SET/CREATE INDEX/CHECK statements
    assert len(schema.tables) == 4
    assert len(schema.foreign_keys) == 3


def test_inline_column_reference_matches_out_of_line_form() -> None:
    # Arrange
    inline_sql = """
    CREATE TABLE plants (
        id SERIAL PRIMARY KEY
    );
    CREATE TABLE plant_production (
        id SERIAL PRIMARY KEY,
        plant_id INTEGER NOT NULL REFERENCES plants(id)
    );
    """

    # Act
    schema = parse_ddl(inline_sql)

    # Assert
    assert len(schema.foreign_keys) == 1
    fk = schema.foreign_keys[0]
    assert str(fk.source_table) == "public.plant_production"
    assert fk.source_column == "plant_id"
    assert str(fk.target_table) == "public.plants"
    assert fk.target_column == "id"


def test_inline_table_level_foreign_key_matches_out_of_line_form() -> None:
    # Arrange
    inline_sql = """
    CREATE TABLE plants (
        id SERIAL PRIMARY KEY
    );
    CREATE TABLE plant_production (
        id SERIAL PRIMARY KEY,
        plant_id INTEGER NOT NULL,
        FOREIGN KEY (plant_id) REFERENCES plants(id)
    );
    """

    # Act
    schema = parse_ddl(inline_sql)

    # Assert
    assert len(schema.foreign_keys) == 1
    fk = schema.foreign_keys[0]
    assert str(fk.source_table) == "public.plant_production"
    assert fk.target_column == "id"


def test_schema_qualified_alter_matches_unqualified_form() -> None:
    # Arrange
    qualified_sql = """
    CREATE TABLE plants (id SERIAL PRIMARY KEY);
    CREATE TABLE plant_production (id SERIAL PRIMARY KEY, plant_id INTEGER NOT NULL);
    ALTER TABLE ONLY public.plant_production
        ADD CONSTRAINT fk_production_plant
        FOREIGN KEY (plant_id)
        REFERENCES public.plants(id);
    """

    # Act
    schema = parse_ddl(qualified_sql)

    # Assert
    assert len(schema.foreign_keys) == 1
    fk = schema.foreign_keys[0]
    assert str(fk.source_table) == "public.plant_production"
    assert str(fk.target_table) == "public.plants"


def test_missing_target_fk_is_skipped_without_crashing(capsys: pytest.CaptureFixture[str]) -> None:
    # Arrange
    sql = """
    CREATE TABLE plant_production (id SERIAL PRIMARY KEY, plant_id INTEGER NOT NULL);
    ALTER TABLE ONLY plant_production
        ADD CONSTRAINT fk_production_plant
        FOREIGN KEY (plant_id)
        REFERENCES plants(id);
    """

    # Act
    schema = parse_ddl(sql)

    # Assert
    assert schema.foreign_keys == []
    captured = capsys.readouterr()
    assert "warning" in captured.err.lower()


def test_schema_filter_excludes_other_schemas() -> None:
    # Arrange
    sql = """
    CREATE TABLE public.plants (id SERIAL PRIMARY KEY);
    CREATE TABLE reporting.summary (id SERIAL PRIMARY KEY);
    """

    # Act
    schema = parse_ddl(sql, schema_filter="public")

    # Assert
    assert set(schema.tables) == {TableId("public", "plants")}


def test_unqualified_and_schema_qualified_table_names_are_the_same_identity() -> None:
    # Arrange
    sql = """
    CREATE TABLE plants (id SERIAL PRIMARY KEY);
    CREATE TABLE plant_production (id SERIAL PRIMARY KEY, plant_id INTEGER NOT NULL);
    ALTER TABLE ONLY public.plant_production
        ADD CONSTRAINT fk_production_plant
        FOREIGN KEY (plant_id)
        REFERENCES plants(id);
    """

    # Act
    schema = parse_ddl(sql)

    # Assert: the unqualified CREATE and qualified ALTER resolve to one table
    assert set(schema.tables) == {
        TableId("public", "plants"),
        TableId("public", "plant_production"),
    }
    assert len(schema.foreign_keys) == 1


def test_quoted_identifiers_preserve_case_unquoted_fold_to_lowercase() -> None:
    # Arrange
    sql = """
    CREATE TABLE "Plants" (id SERIAL PRIMARY KEY);
    CREATE TABLE PLANTS (id SERIAL PRIMARY KEY);
    """

    # Act
    schema = parse_ddl(sql)

    # Assert: quoted "Plants" keeps case; unquoted PLANTS folds to lowercase "plants"
    assert set(schema.tables) == {
        TableId("public", "Plants"),
        TableId("public", "plants"),
    }


def test_composite_multi_column_foreign_key_pairs_columns_positionally() -> None:
    # Arrange
    sql = """
    CREATE TABLE parent (a INTEGER, b INTEGER, PRIMARY KEY (a, b));
    CREATE TABLE child (
        x INTEGER,
        y INTEGER,
        FOREIGN KEY (x, y) REFERENCES parent(a, b)
    );
    """

    # Act
    schema = parse_ddl(sql)

    # Assert: each source column maps to its corresponding target column, not
    # all source columns collapsing onto the first target column.
    fk_pairs = {(fk.source_column, fk.target_column) for fk in schema.foreign_keys}
    assert fk_pairs == {("x", "a"), ("y", "b")}


def test_self_referencing_foreign_key() -> None:
    # Arrange
    sql = """
    CREATE TABLE employees (
        id SERIAL PRIMARY KEY,
        manager_id INTEGER REFERENCES employees(id)
    );
    """

    # Act
    schema = parse_ddl(sql)

    # Assert
    assert len(schema.foreign_keys) == 1
    fk = schema.foreign_keys[0]
    assert fk.source_table == fk.target_table == TableId("public", "employees")
    assert fk.source_column == "manager_id"
    assert fk.target_column == "id"


def test_table_with_zero_foreign_keys_has_none() -> None:
    # Arrange
    sql = "CREATE TABLE standalone (id SERIAL PRIMARY KEY, note TEXT);"

    # Act
    schema = parse_ddl(sql)

    # Assert
    assert set(schema.tables) == {TableId("public", "standalone")}
    assert schema.foreign_keys == []


def test_inline_reference_without_column_list_resolves_to_parent_pk() -> None:
    # Arrange
    sql = """
    CREATE TABLE plants (id SERIAL PRIMARY KEY);
    CREATE TABLE child (id INT, parent_id INT REFERENCES plants);
    """

    # Act
    schema = parse_ddl(sql)

    # Assert
    assert len(schema.foreign_keys) == 1
    fk = schema.foreign_keys[0]
    assert fk.source_column == "parent_id"
    assert fk.target_column == "id"


def test_alter_reference_without_column_list_resolves_to_parent_pk() -> None:
    # Arrange
    sql = """
    CREATE TABLE plants (id SERIAL PRIMARY KEY);
    CREATE TABLE child (id INT, parent_id INT);
    ALTER TABLE ONLY child
        ADD CONSTRAINT fk_child_plant
        FOREIGN KEY (parent_id)
        REFERENCES plants;
    """

    # Act
    schema = parse_ddl(sql)

    # Assert
    assert len(schema.foreign_keys) == 1
    fk = schema.foreign_keys[0]
    assert fk.source_column == "parent_id"
    assert fk.target_column == "id"


def test_reference_without_column_list_and_no_parent_pk_is_skipped_with_warning(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    sql = """
    CREATE TABLE plants (id INT);
    CREATE TABLE child (id INT, parent_id INT REFERENCES plants);
    """

    # Act
    schema = parse_ddl(sql)

    # Assert
    assert schema.foreign_keys == []
    captured = capsys.readouterr()
    assert "warning" in captured.err.lower()
    assert "primary key" in captured.err.lower()


def test_composite_fk_column_count_mismatch_is_skipped_entirely_with_warning(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    sql = """
    CREATE TABLE parent (a INTEGER, b INTEGER, PRIMARY KEY (a, b));
    CREATE TABLE child (
        a INTEGER,
        b INTEGER,
        FOREIGN KEY (a, b) REFERENCES parent (a)
    );
    """

    # Act
    schema = parse_ddl(sql)

    # Assert: neither "a -> a" nor any partial pairing is emitted
    assert schema.foreign_keys == []
    captured = capsys.readouterr()
    assert "warning" in captured.err.lower()


def test_malformed_sql_raises_ddl_parse_error() -> None:
    # Arrange
    bad_sql = "CREATE TABLE (((( broken"

    # Act / Assert
    with pytest.raises(DdlParseError):
        parse_ddl(bad_sql)
