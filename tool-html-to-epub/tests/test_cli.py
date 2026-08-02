"""End-to-end CLI tests: build, validate, determinism."""

import filecmp
import time
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import pytest

import html_to_epub.cli as cli_module
import html_to_epub.pipeline as pipeline_module
from html_to_epub.cli import main
from html_to_epub.fetch import FetchedPage

FIXTURES = Path(__file__).parent / "fixtures"


def _stub_fetch(monkeypatch: pytest.MonkeyPatch, pages: dict[str, str]) -> None:
    """Serve `pages` (url -> raw html) in place of a real network fetch."""

    def fake(url: str, *, timeout: float = 20.0, user_agent: str | None = None) -> FetchedPage:
        return FetchedPage(url=url, final_url=url, html=pages[url])

    monkeypatch.setattr(pipeline_module, "fetch_url", fake)
    monkeypatch.setattr(cli_module, "fetch_url", fake)


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


_PAGE_ONE = """<html><head><title>Page One</title></head><body>
<nav>nav junk</nav>
<article><h1>Page One</h1><p>First page content with enough real prose to be recognized as
the main article body by the extraction heuristics used in this pipeline for testing.</p></article>
<footer>footer junk</footer>
</body></html>"""

_PAGE_TWO = """<html><head><title>Page Two</title></head><body>
<nav>nav junk</nav>
<article><h1>Page Two</h1><p>Second page content with enough real prose to be recognized as
the main article body by the extraction heuristics used in this pipeline for testing.</p></article>
<footer>footer junk</footer>
</body></html>"""


def test_multi_url_build_yields_one_chapter_per_url_in_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    urls = ["https://example.com/one", "https://example.com/two"]
    _stub_fetch(monkeypatch, {urls[0]: _PAGE_ONE, urls[1]: _PAGE_TWO})

    out = tmp_path / "multi.epub"
    rc = main(["build", urls[0], "--url-list", _write_url_list(tmp_path, urls[1:]), "-o", str(out)])
    assert rc == 0
    with zipfile.ZipFile(out) as zf:
        chapter_names = sorted(n for n in zf.namelist() if n.startswith("EPUB/chap_"))
        assert len(chapter_names) == 2
        assert b"Page One" in zf.read(chapter_names[0])
        assert b"Page Two" in zf.read(chapter_names[1])


def test_fetch_writes_deterministic_files_and_build_is_repeatable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    urls = ["https://example.com/one", "https://example.com/two"]
    _stub_fetch(monkeypatch, {urls[0]: _PAGE_ONE, urls[1]: _PAGE_TWO})

    fetch_dir = tmp_path / "fetched"
    url_list = _write_url_list(tmp_path, urls[1:])
    rc = main(["fetch", urls[0], "--url-list", url_list, "-o", str(fetch_dir)])
    assert rc == 0
    files = sorted(p.name for p in fetch_dir.iterdir())
    assert files == ["0000-example-com-one.html", "0001-example-com-two.html"]

    out1 = tmp_path / "a.epub"
    out2 = tmp_path / "b.epub"
    main(["build", str(fetch_dir), "-o", str(out1)])
    time.sleep(1.1)
    main(["build", str(fetch_dir), "-o", str(out2)])
    assert filecmp.cmp(out1, out2, shallow=False)


def test_metadata_precedence_cli_beats_sidecar_beats_extracted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = "https://example.com/one"
    _stub_fetch(monkeypatch, {url: _PAGE_ONE})
    sidecar = FIXTURES / "meta.toml"

    out = tmp_path / "meta.epub"
    rc = main(["build", url, "-o", str(out), "--metadata", str(sidecar), "--title", "CLI Wins"])
    assert rc == 0
    rc = main(["inspect", url, "--metadata", str(sidecar)])
    assert rc == 0


def test_build_with_bad_scheme_url_reports_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "out.epub"
    url_list = _write_url_list(tmp_path, ["ftp://example.com/file.html"])
    rc = main(["build", "--url-list", url_list, "-o", str(out)])
    assert rc == 1
    assert "[error]" in capsys.readouterr().err


def test_build_with_bad_scheme_positional_reports_scheme_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "out.epub"
    rc = main(["build", "ftp://example.com/file.html", "-o", str(out)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "[error]" in err
    assert "unsupported URL scheme: ftp" in err


def test_build_rejects_local_path_combined_with_url_list(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "out.epub"
    url_list = _write_url_list(tmp_path, ["https://example.com/one"])
    rc = main(["build", str(FIXTURES / "single.html"), "--url-list", url_list, "-o", str(out)])
    assert rc == 1
    assert "[error]" in capsys.readouterr().err
    assert not out.exists()


def test_fetch_rejects_local_path_combined_with_url_list(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fetch_dir = tmp_path / "fetched"
    url_list = _write_url_list(tmp_path, ["https://example.com/one"])
    rc = main(
        ["fetch", str(FIXTURES / "single.html"), "--url-list", url_list, "-o", str(fetch_dir)]
    )
    assert rc == 1
    assert "[error]" in capsys.readouterr().err


def _write_url_list(tmp_path: Path, urls: list[str]) -> str:
    path = tmp_path / "urls.txt"
    path.write_text("\n".join(["# comment", *urls, ""]), encoding="utf-8")
    return str(path)
