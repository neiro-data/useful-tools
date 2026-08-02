"""End-to-end CLI tests."""

from __future__ import annotations

import filecmp
import os
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import pytest

from pdf_to_epub import ocr as ocr_module
from pdf_to_epub.cli import main
from tests.fixtures import make_pdfs


def test_build_then_validate_round_trip(tmp_path: Path) -> None:
    pdf_path = make_pdfs.make_single_column(tmp_path, pages=2)
    out_path = tmp_path / "out.epub"

    assert main(["build", str(pdf_path), "-o", str(out_path)]) == 0
    assert main(["validate", str(out_path)]) == 0


def test_build_is_byte_deterministic(tmp_path: Path) -> None:
    pdf_path = make_pdfs.make_single_column(tmp_path, pages=2)
    out_a = tmp_path / "a.epub"
    out_b = tmp_path / "b.epub"

    assert main(["build", str(pdf_path), "-o", str(out_a)]) == 0
    time.sleep(1.1)
    assert main(["build", str(pdf_path), "-o", str(out_b)]) == 0

    assert filecmp.cmp(out_a, out_b, shallow=False)


def test_two_column_reading_order_in_output(tmp_path: Path) -> None:
    pdf_path = make_pdfs.make_two_column(tmp_path, pages=1)
    out_path = tmp_path / "out.epub"

    assert main(["build", str(pdf_path), "-o", str(out_path)]) == 0

    import zipfile

    with zipfile.ZipFile(out_path) as zf:
        chapter_files = [n for n in zf.namelist() if n.endswith(".xhtml") and "chap" in n]
        text = "".join(zf.read(n).decode() for n in sorted(chapter_files))

    left0 = make_pdfs._LEFT_SENTENCES[0]
    right0 = make_pdfs._RIGHT_SENTENCES[0]
    assert text.index(left0) < text.index(right0)


def test_scanned_without_ocr_flag_exits_1(tmp_path: Path) -> None:
    pdf_path = make_pdfs.make_scanned(tmp_path)
    out_path = tmp_path / "out.epub"

    exit_code = main(["build", str(pdf_path), "-o", str(out_path)])

    assert exit_code == 1


def test_scanned_without_ocr_flag_message_names_ocr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pdf_path = make_pdfs.make_scanned(tmp_path)
    out_path = tmp_path / "out.epub"

    main(["build", str(pdf_path), "-o", str(out_path)])

    captured = capsys.readouterr()
    assert "--ocr" in captured.err


def test_scanned_with_ocr_but_missing_binary_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf_path = make_pdfs.make_scanned(tmp_path)
    out_path = tmp_path / "out.epub"

    monkeypatch.setattr(ocr_module.shutil, "which", lambda _name: None)

    exit_code = main(["build", str(pdf_path), "-o", str(out_path), "--ocr"])

    assert exit_code == 1


def test_min_confidence_rejects_messy_document(tmp_path: Path) -> None:
    pdf_path = make_pdfs.make_messy(tmp_path)
    out_path = tmp_path / "out.epub"

    default_exit = main(["build", str(pdf_path), "-o", str(out_path)])
    strict_exit = main(
        ["build", str(pdf_path), "-o", str(tmp_path / "strict.epub"), "--min-confidence", "0.99"]
    )

    assert strict_exit == 1
    assert default_exit == 0


def test_inspect_prints_per_page_lines(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    pdf_path = make_pdfs.make_single_column(tmp_path, pages=2)

    exit_code = main(["inspect", str(pdf_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "page 1" in captured.out


def test_classify_prints_per_page_lines(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    pdf_path = make_pdfs.make_single_column(tmp_path, pages=2)

    exit_code = main(["classify", str(pdf_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "page 1" in captured.out


def test_build_is_byte_deterministic_across_fresh_processes(tmp_path: Path) -> None:
    pdf_path = make_pdfs.make_single_column(tmp_path, pages=2)
    out_a = tmp_path / "proc_a.epub"
    out_b = tmp_path / "proc_b.epub"

    for out_path in (out_a, out_b):
        result = subprocess.run(  # noqa: S603 - fixed argv, no shell, no untrusted input
            [
                sys.executable,
                "-m",
                "pdf_to_epub.cli",
                "build",
                str(pdf_path),
                "-o",
                str(out_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr

    assert filecmp.cmp(out_a, out_b, shallow=False)


def test_build_is_byte_deterministic_across_hash_seeds(tmp_path: Path) -> None:
    pdf_path = make_pdfs.make_single_column(tmp_path, pages=2)
    out_a = tmp_path / "seed_a.epub"
    out_b = tmp_path / "seed_b.epub"

    for seed, out_path in (("1", out_a), ("2", out_b)):
        result = subprocess.run(  # noqa: S603 - fixed argv, no shell, no untrusted input
            [
                sys.executable,
                "-m",
                "pdf_to_epub.cli",
                "build",
                str(pdf_path),
                "-o",
                str(out_path),
            ],
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "PYTHONHASHSEED": seed},
        )
        assert result.returncode == 0, result.stderr

    assert filecmp.cmp(out_a, out_b, shallow=False)


def test_build_on_corrupt_pdf_reports_error_without_traceback(tmp_path: Path) -> None:
    bad_pdf = tmp_path / "bad.pdf"
    bad_pdf.write_bytes(b"%PDF-1.4")
    out_path = tmp_path / "out.epub"

    result = subprocess.run(  # noqa: S603 - fixed argv, no shell, no untrusted input
        [sys.executable, "-m", "pdf_to_epub.cli", "build", str(bad_pdf), "-o", str(out_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "[error]" in result.stderr
    assert "Traceback" not in result.stderr


def test_build_on_missing_file_reports_error(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist.pdf"
    out_path = tmp_path / "out.epub"

    assert main(["build", str(missing), "-o", str(out_path)]) == 1


def test_build_on_directory_input_reports_error(tmp_path: Path) -> None:
    directory = tmp_path / "a_dir.pdf"
    directory.mkdir()
    out_path = tmp_path / "out.epub"

    assert main(["build", str(directory), "-o", str(out_path)]) == 1


def test_metadata_sidecar_overrides_title_and_author(tmp_path: Path) -> None:
    pdf_path = make_pdfs.make_single_column(tmp_path, pages=1)
    metadata_path = tmp_path / "meta.toml"
    metadata_path.write_text('title = "Custom Title"\nauthor = "Custom Author"\n', encoding="utf-8")
    out_path = tmp_path / "out.epub"

    exit_code = main(
        ["build", str(pdf_path), "-o", str(out_path), "--metadata", str(metadata_path)]
    )

    assert exit_code == 0
    with zipfile.ZipFile(out_path) as zf:
        opf_name = next(n for n in zf.namelist() if n.endswith(".opf"))
        opf_text = zf.read(opf_name).decode()
    assert "Custom Title" in opf_text
    assert "Custom Author" in opf_text


def test_no_tables_flag_omits_table_from_output(tmp_path: Path) -> None:
    pdf_path = make_pdfs.make_table_page(tmp_path)
    out_with_tables = tmp_path / "with_tables.epub"
    out_without_tables = tmp_path / "without_tables.epub"

    assert main(["build", str(pdf_path), "-o", str(out_with_tables)]) == 0
    assert main(["build", str(pdf_path), "-o", str(out_without_tables), "--no-tables"]) == 0

    def chapter_text(path: Path) -> str:
        with zipfile.ZipFile(path) as zf:
            chapter_files = [n for n in zf.namelist() if n.endswith(".xhtml") and "chap" in n]
            return "".join(zf.read(n).decode() for n in sorted(chapter_files))

    assert "<table" in chapter_text(out_with_tables)
    assert "<table" not in chapter_text(out_without_tables)


def test_split_level_two_produces_more_chapters(tmp_path: Path) -> None:
    pdf_path = make_pdfs.make_with_headings(tmp_path)
    out_1 = tmp_path / "split1.epub"
    out_2 = tmp_path / "split2.epub"

    assert main(["build", str(pdf_path), "-o", str(out_1)]) == 0
    assert main(["build", str(pdf_path), "-o", str(out_2), "--split-level", "2"]) == 0

    import zipfile

    def chapter_count(path: Path) -> int:
        with zipfile.ZipFile(path) as zf:
            return len([n for n in zf.namelist() if "chap_" in n])

    assert chapter_count(out_2) > chapter_count(out_1)
