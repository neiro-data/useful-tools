"""End-to-end CLI tests: build, validate, determinism."""

import filecmp
import time
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from html_to_epub.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def test_build_single_html_produces_valid_epub(tmp_path: Path) -> None:
    out = tmp_path / "out.epub"
    rc = main(["build", str(FIXTURES / "single.html"), "-o", str(out)])
    assert rc == 0
    assert out.exists()
    rc = main(["validate", str(out)])
    assert rc == 0


def test_build_directory_produces_valid_epub(tmp_path: Path) -> None:
    out = tmp_path / "book.epub"
    rc = main(["build", str(FIXTURES / "book"), "-o", str(out)])
    assert rc == 0
    rc = main(["validate", str(out)])
    assert rc == 0


def test_build_with_metadata_sidecar(tmp_path: Path) -> None:
    out = tmp_path / "meta.epub"
    rc = main(
        [
            "build",
            str(FIXTURES / "single.html"),
            "-o",
            str(out),
            "--metadata",
            str(FIXTURES / "meta.toml"),
        ]
    )
    assert rc == 0
    assert out.exists()


def test_inspect_writes_nothing(tmp_path: Path, capsys: object) -> None:
    rc = main(["inspect", str(FIXTURES / "book")])
    assert rc == 0
    assert list(tmp_path.iterdir()) == []


def test_validate_nonexistent_file_fails(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.epub"
    rc = main(["validate", str(missing)])
    assert rc != 0


def test_build_is_deterministic(tmp_path: Path) -> None:
    out1 = tmp_path / "a.epub"
    out2 = tmp_path / "b.epub"
    main(["build", str(FIXTURES / "book"), "-o", str(out1)])
    time.sleep(1.1)  # cross a wall-clock second boundary
    main(["build", str(FIXTURES / "book"), "-o", str(out2)])
    assert filecmp.cmp(out1, out2, shallow=False)


def test_chapter_xhtml_files_contain_body_content(tmp_path: Path) -> None:
    out = tmp_path / "out.epub"
    main(["build", str(FIXTURES / "single.html"), "-o", str(out)])
    with zipfile.ZipFile(out) as zf:
        chapter_names = [n for n in zf.namelist() if n.startswith("EPUB/chap_")]
        assert chapter_names, "no chapter files written"
        for name in chapter_names:
            data = zf.read(name)
            assert data, f"{name} is empty"
            root = ElementTree.fromstring(data)  # noqa: S314 - reading our own generated file
            assert root.tag.endswith("html")
