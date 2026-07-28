"""Tests for ddl_to_drawio.cli."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from ddl_to_drawio.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "sample_plants.sql"


def test_stdin_stdout_round_trip(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    monkeypatch.setattr("sys.stdin", io.StringIO(FIXTURE.read_text(encoding="utf-8")))

    # Act
    exit_code = main(["-", "-o", "-"])

    # Assert
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "<mxfile" in out
    assert out.count('edge="1"') == 3


def test_schema_filter_produces_no_matching_tables_and_fails(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Act
    exit_code = main([str(FIXTURE), "--schema", "nonexistent", "-o", "-"])

    # Assert
    assert exit_code != 0
    assert "no tables found" in capsys.readouterr().err


def test_malformed_sql_exits_non_zero_with_useful_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Arrange
    bad_file = tmp_path / "bad.sql"
    bad_file.write_text("CREATE TABLE (((( broken", encoding="utf-8")

    # Act
    exit_code = main([str(bad_file), "-o", "-"])

    # Assert
    assert exit_code != 0
    err = capsys.readouterr().err
    assert "error" in err.lower()


def test_writes_drawio_file_with_default_output_name(tmp_path: Path) -> None:
    # Arrange
    input_file = tmp_path / "dump.sql"
    input_file.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")

    # Act
    exit_code = main([str(input_file)])

    # Assert
    expected_output = tmp_path / "dump.drawio"
    assert exit_code == 0
    assert expected_output.exists()
    assert "<mxfile" in expected_output.read_text(encoding="utf-8")
