"""OCR invocation. Sole importer of ``subprocess`` in this library."""

from __future__ import annotations

import shutil as shutil  # re-exported so tests can monkeypatch ocr.shutil
import subprocess as subprocess  # noqa: S404 - the one sanctioned import site for subprocess
from pathlib import Path


class OcrError(Exception):
    """Raised when ``ocrmypdf`` is unavailable or fails."""


def ocr_available() -> bool:
    """Return True if the ``ocrmypdf`` binary is discoverable on PATH."""
    return shutil.which("ocrmypdf") is not None


def run_ocr(src: Path, dest: Path) -> None:
    """Run ``ocrmypdf --skip-text`` on ``src``, writing the result to ``dest``."""
    binary = shutil.which("ocrmypdf")
    if binary is None:
        raise OcrError("ocrmypdf binary not found on PATH")

    result = subprocess.run(  # noqa: S603 - args is a fixed list, no shell
        [binary, "--skip-text", str(src), str(dest)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        tail = result.stderr[-2000:] if result.stderr else ""
        raise OcrError(f"ocrmypdf failed with exit code {result.returncode}: {tail}")
