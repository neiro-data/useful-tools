"""Derive a safe output filename from a title/url, applying the configured template.

Reuses html_to_epub.pipeline.slugify_url for the slug shape rather than reimplementing it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from html_to_epub.pipeline import slugify_url


class PathTraversalError(Exception):
    """Raised when a resolved output path escapes the configured output directory."""


def build_slug(title: str | None, url: str) -> str:
    """Derive a filesystem-safe slug from a title, falling back to the URL shape."""
    if title and title.strip():
        return str(slugify_url(title.strip()))
    return str(slugify_url(url))


def render_filename(template: str, *, title: str | None, url: str) -> str:
    """Render the filename template with {date} and {slug} placeholders."""
    slug = build_slug(title, url)
    date = datetime.now(tz=UTC).strftime("%Y-%m-%d")
    name = template.format(date=date, slug=slug)
    if not name.lower().endswith(".epub"):
        name += ".epub"
    return name


def resolve_output_path(
    output_dir: str,
    filename: str,
    *,
    overwrite: bool,
) -> Path:
    """Resolve `filename` inside `output_dir`, guarding against traversal and collisions.

    Raises:
        PathTraversalError: if the resolved path would land outside `output_dir`.
    """
    base = Path(output_dir).expanduser().resolve()
    base.mkdir(parents=True, exist_ok=True)

    # Strip any path components/NUL bytes from the caller-controlled filename; only the
    # basename is trusted, everything else is derived server-side (template + slug).
    safe_name = Path(filename.replace("\x00", "")).name
    if not safe_name or safe_name in {".", ".."}:
        safe_name = "page.epub"

    candidate = (base / safe_name).resolve()
    _assert_within(candidate, base)

    if overwrite or not candidate.exists():
        return candidate

    stem, suffix = candidate.stem, candidate.suffix
    counter = 2
    while True:
        candidate = (base / f"{stem}-{counter}{suffix}").resolve()
        _assert_within(candidate, base)
        if not candidate.exists():
            return candidate
        counter += 1


def _assert_within(candidate: Path, base: Path) -> None:
    if candidate != base and base not in candidate.parents:
        raise PathTraversalError(f"resolved path {candidate} escapes output_dir {base}")


__all__ = ["PathTraversalError", "build_slug", "render_filename", "resolve_output_path"]
