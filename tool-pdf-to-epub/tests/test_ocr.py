"""Tests for the OCR wrapper. Never invokes the real ocrmypdf binary."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from pdf_to_epub import ocr


def test_ocr_available_true_when_binary_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ocr.shutil, "which", lambda _name: "/usr/bin/ocrmypdf")
    assert ocr.ocr_available() is True


def test_ocr_available_false_when_binary_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ocr.shutil, "which", lambda _name: None)
    assert ocr.ocr_available() is False


def test_run_ocr_raises_when_binary_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(ocr.shutil, "which", lambda _name: None)

    with pytest.raises(ocr.OcrError, match="not found"):
        ocr.run_ocr(tmp_path / "src.pdf", tmp_path / "dest.pdf")


def test_run_ocr_raises_on_nonzero_exit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(ocr.shutil, "which", lambda _name: "/usr/bin/ocrmypdf")

    def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["ocrmypdf"], returncode=1, stdout="", stderr="boom: page corrupt"
        )

    monkeypatch.setattr(ocr.subprocess, "run", fake_run)

    with pytest.raises(ocr.OcrError, match="boom"):
        ocr.run_ocr(tmp_path / "src.pdf", tmp_path / "dest.pdf")


def test_run_ocr_succeeds_when_binary_and_exit_code_are_fine(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(ocr.shutil, "which", lambda _name: "/usr/bin/ocrmypdf")

    def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=["ocrmypdf"], returncode=0, stdout="", stderr="")

    monkeypatch.setattr(ocr.subprocess, "run", fake_run)

    ocr.run_ocr(tmp_path / "src.pdf", tmp_path / "dest.pdf")
