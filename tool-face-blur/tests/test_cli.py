from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from face_blur import cli, server


def test_auto_writes_output(
    face_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "out.jpg"
    boxes = tmp_path / "boxes.json"
    code = cli.main(
        ["auto", str(face_path), str(out), "--method", "solid", "--boxes-json", str(boxes)]
    )
    assert code == 0
    assert "1 faces blurred" in capsys.readouterr().out
    with Image.open(out) as img, Image.open(face_path) as src:
        assert img.size == src.size
        assert len(img.getexif()) == 0
    assert len(json.loads(boxes.read_text())) == 1


def test_auto_no_faces_still_writes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    src = tmp_path / "blank.png"
    Image.new("RGB", (64, 64), (120, 120, 120)).save(src)
    out = tmp_path / "o.png"
    assert cli.main(["auto", str(src), str(out)]) == 0
    assert out.is_file()
    captured = capsys.readouterr()
    assert "0 faces blurred" in captured.out and "warning" in captured.err


def test_detect_prints_json(face_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["detect", str(face_path)]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["width"] == 330 and len(data["faces"]) >= 1


def test_bad_path_exit_2(tmp_path: Path) -> None:
    assert cli.main(["auto", str(tmp_path / "missing.jpg"), str(tmp_path / "o.jpg")]) == 2
    assert cli.main(["detect", str(tmp_path / "missing.jpg")]) == 2


def test_bad_input_and_output_ext_exit_2(face_path: Path, tmp_path: Path) -> None:
    junk = tmp_path / "junk.jpg"
    junk.write_text("nope")
    assert cli.main(["auto", str(junk), str(tmp_path / "o.jpg")]) == 2
    assert cli.main(["auto", str(face_path), str(tmp_path / "o.bmp")]) == 2


def test_bad_args_exit_2(face_path: Path, tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["auto", str(face_path), str(tmp_path / "o.jpg"), "--method", "bogus"])
    assert exc.value.code == 2
    assert cli.main(["auto", str(face_path), str(tmp_path / "o.jpg"), "--padding", "5"]) == 2


def test_serve_warns_on_nonlocal_host(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[tuple[str, int, bool]] = []
    monkeypatch.setattr(
        server, "run", lambda h, p, open_browser: calls.append((h, p, open_browser))
    )
    assert cli.main(["serve", "--host", "0.0.0.0", "--port", "9", "--no-browser"]) == 0  # noqa: S104
    assert calls == [("0.0.0.0", 9, False)]  # noqa: S104
    assert "warning" in capsys.readouterr().err
    calls.clear()
    cli.main(["serve", "--no-browser"])
    assert calls == [("127.0.0.1", 8765, False)]


@pytest.mark.parametrize("value", ["0", "-5"])
def test_max_side_must_be_positive(face_path: Path, tmp_path: Path, value: str) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["detect", str(face_path), "--max-side", value])
    assert exc.value.code == 2
    with pytest.raises(SystemExit) as exc2:
        cli.main(["auto", str(face_path), str(tmp_path / "o.jpg"), "--max-side", value])
    assert exc2.value.code == 2
