"""Local Flask server: stateless JSON/multipart API plus the static UI."""

from __future__ import annotations

import json
import sys
import threading
import webbrowser
from importlib import resources
from pathlib import Path
from typing import Any, cast

from flask import Flask, Response, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException
from werkzeug.utils import secure_filename

from . import blur, imageio, pipeline
from .regions import Region

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_REGIONS = 500
DEFAULT_HOST = "127.0.0.1"


class ApiError(Exception):
    """Error mapped to a JSON ``{"error": ...}`` response."""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


def _error(message: str, status: int) -> tuple[Response, int]:
    return jsonify({"error": message}), status


def _read_image() -> tuple[Any, str]:
    upload = request.files.get("image")
    if upload is None:
        raise ApiError("Missing 'image' file field")
    try:
        rgb = imageio.load_bytes(upload.read())
    except imageio.ImageError as exc:
        raise ApiError(str(exc), 415) from exc
    stem = Path(secure_filename(upload.filename or "")).stem or "image"
    return rgb, stem


def _float_field(value: str | None, name: str, lo: float, hi: float) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except ValueError as exc:
        raise ApiError(f"{name} must be a number") from exc
    if not lo <= number <= hi:
        raise ApiError(f"{name} must be between {lo} and {hi}")
    return number


def _params() -> dict[str, Any]:
    raw = request.form.get("params")
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ApiError("params is not valid JSON") from exc
    if not isinstance(data, dict):
        raise ApiError("params must be a JSON object")
    return data


def _int_param(params: dict[str, Any], key: str, default: int, lo: int, hi: int) -> int:
    value = params.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ApiError(f"{key} must be an integer")
    if not lo <= value <= hi:
        raise ApiError(f"{key} must be between {lo} and {hi}")
    return value


def _choice(params: dict[str, Any], key: str, default: str, allowed: tuple[str, ...]) -> str:
    value = params.get(key, default)
    if value not in allowed:
        raise ApiError(f"{key} must be one of {', '.join(allowed)}")
    return cast(str, value)


def _padding(params: dict[str, Any], default: float) -> float:
    value = params.get("padding", default)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ApiError("padding must be a number")
    if not 0 <= value <= 0.5:
        raise ApiError("padding must be between 0 and 0.5")
    return float(value)


def _respond(rgb: Any, stem: str, params: dict[str, Any]) -> Response:
    fmt = _choice(params, "format", "png", tuple(imageio.MIME))
    quality = _int_param(params, "quality", 92, 1, 100)
    body = imageio.encode(rgb, fmt, quality)
    response = Response(body, mimetype=imageio.MIME[fmt])
    response.headers["Content-Disposition"] = (
        f'attachment; filename="{stem}-blurred.{imageio.EXT[fmt]}"'
    )
    return response


def create_app() -> Flask:
    """Build the Flask application."""
    static_dir = Path(str(resources.files("face_blur").joinpath("static")))
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES

    @app.errorhandler(ApiError)
    def _api_error(exc: ApiError) -> tuple[Response, int]:
        return _error(exc.message, exc.status)

    @app.errorhandler(HTTPException)
    def _http_error(exc: HTTPException) -> tuple[Response, int]:
        return _error(exc.description or exc.name, exc.code or 500)

    @app.errorhandler(Exception)
    def _unexpected(exc: Exception) -> tuple[Response, int]:
        app.logger.exception("Unhandled error", exc_info=exc)
        return _error("Internal server error", 500)

    @app.get("/")
    def index() -> Response:
        return send_from_directory(static_dir, "index.html")

    @app.get("/static/<path:name>")
    def static_file(name: str) -> Response:
        return send_from_directory(static_dir, name)

    @app.post("/api/detect")
    def detect() -> Response:
        rgb, _ = _read_image()
        min_score = _float_field(request.form.get("min_score"), "min_score", 0.0, 1.0)
        faces = pipeline.detect(rgb, min_score)
        return jsonify(
            {
                "width": int(rgb.shape[1]),
                "height": int(rgb.shape[0]),
                "faces": [
                    {"id": i, "x": f.x, "y": f.y, "w": f.w, "h": f.h, "score": f.score}
                    for i, f in enumerate(faces)
                ],
            }
        )

    @app.post("/api/blur")
    def blur_regions() -> Response:
        rgb, stem = _read_image()
        params = _params()
        method = _choice(params, "method", "gaussian", blur.METHODS)
        strength = _int_param(params, "strength", 5, 1, 10)
        padding = _padding(params, 0.15)
        raw_regions = params.get("regions", [])
        if not isinstance(raw_regions, list) or len(raw_regions) > MAX_REGIONS:
            raise ApiError(f"regions must be a list of at most {MAX_REGIONS} items")
        height, width = rgb.shape[:2]
        regions: list[Region] = []
        for item in raw_regions:
            try:
                region = Region.from_dict(item)
            except ValueError as exc:
                raise ApiError(f"Invalid region: {exc}") from exc
            if region.shape == "ellipse" or region.source == "auto":
                region = region.pad(padding)
            clamped = region.clamp(width, height)
            if clamped is not None:
                regions.append(clamped)
        return _respond(blur.apply(rgb, regions, method, strength), stem, params)

    @app.post("/api/auto")
    def auto() -> Response:
        rgb, stem = _read_image()
        params = _params()
        try:
            opts = pipeline.AutoOptions(
                method=_choice(params, "method", "gaussian", blur.METHODS),
                strength=_int_param(params, "strength", 5, 1, 10),
                shape=_choice(params, "shape", "ellipse", ("ellipse", "rect")),
                padding=_padding(params, 0.15),
                min_score=_float_field(request.form.get("min_score"), "min_score", 0.0, 1.0),
            )
        except ValueError as exc:
            raise ApiError(str(exc)) from exc
        out, _ = pipeline.auto_blur(rgb, opts)
        return _respond(out, stem, params)

    return app


def run(host: str = DEFAULT_HOST, port: int = 8765, open_browser: bool = True) -> None:
    """Serve the UI (blocking)."""
    if host != DEFAULT_HOST:
        print(f"warning: binding to {host} exposes the tool beyond this machine", file=sys.stderr)
    app = create_app()
    if open_browser:
        url = f"http://{'127.0.0.1' if host in ('0.0.0.0', '') else host}:{port}/"  # noqa: S104
        threading.Timer(0.8, webbrowser.open, args=(url,)).start()
    app.run(host=host, port=port, threaded=True, debug=False)
