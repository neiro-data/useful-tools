from __future__ import annotations

import io
import json
from collections.abc import Iterator
from typing import Any

import pytest
from flask import Flask
from flask.testing import FlaskClient
from PIL import Image

from face_blur import pipeline, server
from face_blur.regions import Region


@pytest.fixture
def client() -> Iterator[FlaskClient]:
    app: Flask = server.create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def fake_detect(monkeypatch: pytest.MonkeyPatch) -> None:
    def _detect(
        rgb: Any, min_score: float | None = None, max_side: int | None = None
    ) -> list[Region]:
        return [Region(100, 60, 60, 70, "ellipse", 0.9, "auto")]

    monkeypatch.setattr(pipeline, "detect", _detect)


def _post(
    client: FlaskClient,
    url: str,
    data: bytes,
    params: dict[str, Any] | None = None,
    name: str = "My Photo.jpg",
    **form: str,
) -> Any:
    body: dict[str, Any] = {"image": (io.BytesIO(data), name), **form}
    if params is not None:
        body["params"] = json.dumps(params)
    return client.post(url, data=body, content_type="multipart/form-data")


def test_index_and_static(client: FlaskClient) -> None:
    assert client.get("/").status_code == 200
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/missing.js").status_code == 404
    assert "error" in client.get("/nope").get_json()


def test_detect_schema(client: FlaskClient, face_bytes: bytes, fake_detect: None) -> None:
    r = _post(client, "/api/detect", face_bytes)
    assert r.status_code == 200
    body = r.get_json()
    assert (body["width"], body["height"]) == (330, 412)
    assert body["faces"] == [{"id": 0, "x": 100, "y": 60, "w": 60, "h": 70, "score": 0.9}]


def test_detect_real_end_to_end(client: FlaskClient, face_bytes: bytes) -> None:
    body = _post(client, "/api/detect", face_bytes, min_score="0.5").get_json()
    assert len(body["faces"]) >= 1


def test_blur_returns_same_dims_and_filename(client: FlaskClient, face_bytes: bytes) -> None:
    params = {
        "regions": [{"x": 100, "y": 60, "w": 60, "h": 70, "shape": "ellipse"}],
        "method": "solid",
        "format": "jpeg",
    }
    r = _post(client, "/api/blur", face_bytes, params)
    assert r.status_code == 200
    assert r.mimetype == "image/jpeg"
    assert r.headers["Content-Disposition"] == 'attachment; filename="My_Photo-blurred.jpg"'
    assert Image.open(io.BytesIO(r.data)).size == (330, 412)


def test_blur_changes_pixels(client: FlaskClient, face_bytes: bytes) -> None:
    params = {
        "regions": [{"x": 100, "y": 60, "w": 60, "h": 70, "shape": "rect"}],
        "method": "solid",
    }
    r = _post(client, "/api/blur", face_bytes, params)
    out = Image.open(io.BytesIO(r.data)).convert("RGB")
    assert len({out.getpixel((x, 80)) for x in range(110, 150)}) == 1


def test_auto(client: FlaskClient, face_bytes: bytes, fake_detect: None) -> None:
    r = _post(client, "/api/auto", face_bytes, {"format": "webp", "method": "pixelate"})
    assert r.status_code == 200 and r.mimetype == "image/webp"
    assert r.headers["Content-Disposition"].endswith('-blurred.webp"')


@pytest.mark.parametrize(
    "params",
    [
        {"method": "bogus"},
        {"strength": 99},
        {"strength": "high"},
        {"padding": 0.9},
        {"format": "gif"},
        {"quality": 0},
        {"regions": "x"},
        {"regions": [{"x": 0, "y": 0, "w": 0, "h": 5}]},
        {"regions": [{"x": 0, "y": 0, "w": 5, "h": 5, "shape": "star"}]},
    ],
)
def test_bad_params_400(client: FlaskClient, face_bytes: bytes, params: dict[str, Any]) -> None:
    r = _post(client, "/api/blur", face_bytes, params)
    assert r.status_code == 400
    assert isinstance(r.get_json()["error"], str)


def test_invalid_json_and_missing_image_400(client: FlaskClient, face_bytes: bytes) -> None:
    r = client.post(
        "/api/blur",
        data={"image": (io.BytesIO(face_bytes), "a.jpg"), "params": "{"},
        content_type="multipart/form-data",
    )
    assert r.status_code == 400
    assert (
        client.post("/api/detect", data={}, content_type="multipart/form-data").status_code == 400
    )
    assert _post(client, "/api/detect", face_bytes, min_score="2").status_code == 400


def test_non_image_415(client: FlaskClient) -> None:
    r = _post(client, "/api/detect", b"hello world")
    assert r.status_code == 415
    assert "error" in r.get_json()


def test_oversize_413(client: FlaskClient, monkeypatch: pytest.MonkeyPatch) -> None:
    client.application.config["MAX_CONTENT_LENGTH"] = 1000
    r = _post(client, "/api/detect", b"x" * 5000)
    assert r.status_code == 413
    assert "error" in r.get_json()


def test_non_finite_region_400(client: FlaskClient, face_bytes: bytes) -> None:
    body = {
        "image": (io.BytesIO(face_bytes), "a.jpg"),
        "params": '{"regions": [{"x": Infinity, "y": 0, "w": 5, "h": 5}]}',
    }
    r = client.post("/api/blur", data=body, content_type="multipart/form-data")
    assert r.status_code == 400


def test_unexpected_error_is_json_500(
    client: FlaskClient, face_bytes: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("kaboom")

    monkeypatch.setattr(pipeline, "detect", boom)
    client.application.testing = False
    client.application.config["PROPAGATE_EXCEPTIONS"] = False
    r = _post(client, "/api/detect", face_bytes)
    assert r.status_code == 500
    assert r.get_json() == {"error": "Internal server error"}


def test_run_warns_on_nonlocal_host(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(Flask, "run", lambda *a, **k: None)
    server.run("0.0.0.0", 1, open_browser=False)  # noqa: S104
    assert "warning" in capsys.readouterr().err


@pytest.mark.parametrize("shape", ["ellipse", "rect"])
def test_blur_matches_auto_for_detected_faces(
    client: FlaskClient, face_bytes: bytes, shape: str
) -> None:
    faces = _post(client, "/api/detect", face_bytes).get_json()["faces"]
    assert faces
    regions = [
        {k: f[k] for k in ("x", "y", "w", "h")} | {"shape": shape, "source": "auto"} for f in faces
    ]
    common = {"method": "solid", "strength": 5, "format": "png"}
    blurred = _post(client, "/api/blur", face_bytes, {**common, "regions": regions})
    auto = _post(client, "/api/auto", face_bytes, {**common, "shape": shape})
    assert blurred.status_code == auto.status_code == 200
    assert blurred.data == auto.data


def test_manual_rect_not_padded(client: FlaskClient, face_bytes: bytes) -> None:
    region = {"x": 100, "y": 60, "w": 60, "h": 70, "shape": "rect", "source": "manual"}
    r = _post(client, "/api/blur", face_bytes, {"method": "solid", "regions": [region]})
    out = Image.open(io.BytesIO(r.data)).convert("RGB")
    src = Image.open(io.BytesIO(face_bytes)).convert("RGB")
    assert out.getpixel((95, 90)) == src.getpixel((95, 90))
