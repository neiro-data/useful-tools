from __future__ import annotations

from pathlib import Path

from html_to_epub_server.naming import build_slug, render_filename, resolve_output_path


def test_build_slug_prefers_title() -> None:
    assert build_slug("My Great Article!", "https://example.com/x") == "my-great-article"


def test_build_slug_falls_back_to_url() -> None:
    slug = build_slug(None, "https://example.com/some/path")
    assert slug == "example-com-some-path"


def test_render_filename_appends_epub_extension() -> None:
    name = render_filename("{slug}", title="Hello World", url="https://example.com")
    assert name == "hello-world.epub"


def test_resolve_output_path_stays_inside_output_dir_for_traversal_title(tmp_path: Path) -> None:
    filename = render_filename("{slug}.epub", title="../../etc/passwd", url="https://x.com")
    resolved = resolve_output_path(str(tmp_path), filename, overwrite=True)

    assert resolved.parent == tmp_path.resolve()


def test_resolve_output_path_rejects_absolute_path_component(tmp_path: Path) -> None:
    resolved = resolve_output_path(str(tmp_path), "/etc/passwd", overwrite=True)
    assert resolved.parent == tmp_path.resolve()
    assert resolved.name == "passwd"


def test_resolve_output_path_strips_nul_bytes(tmp_path: Path) -> None:
    resolved = resolve_output_path(str(tmp_path), "evil\x00.epub", overwrite=True)
    assert resolved.parent == tmp_path.resolve()


def test_resolve_output_path_handles_long_titles(tmp_path: Path) -> None:
    long_title = "a" * 300
    filename = render_filename("{slug}.epub", title=long_title, url="https://x.com")
    resolved = resolve_output_path(str(tmp_path), filename, overwrite=True)
    assert resolved.parent == tmp_path.resolve()


def test_resolve_output_path_never_overwrites_by_default(tmp_path: Path) -> None:
    existing = tmp_path / "book.epub"
    existing.write_text("existing", encoding="utf-8")

    resolved = resolve_output_path(str(tmp_path), "book.epub", overwrite=False)

    assert resolved.name == "book-2.epub"


def test_resolve_output_path_suffix_increments_on_repeated_collisions(tmp_path: Path) -> None:
    (tmp_path / "book.epub").write_text("1", encoding="utf-8")
    (tmp_path / "book-2.epub").write_text("2", encoding="utf-8")

    resolved = resolve_output_path(str(tmp_path), "book.epub", overwrite=False)

    assert resolved.name == "book-3.epub"


def test_resolve_output_path_overwrite_true_reuses_same_path(tmp_path: Path) -> None:
    existing = tmp_path / "book.epub"
    existing.write_text("existing", encoding="utf-8")

    resolved = resolve_output_path(str(tmp_path), "book.epub", overwrite=True)

    assert resolved == existing.resolve()
