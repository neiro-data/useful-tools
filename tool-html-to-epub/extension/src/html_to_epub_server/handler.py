"""ThreadingHTTPServer + request handler for POST /convert, GET /health, OPTIONS /convert."""

from __future__ import annotations

import json
import logging
import secrets
from collections.abc import Callable
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from html_to_epub_server import __version__
from html_to_epub_server.config import ServerConfig
from html_to_epub_server.convert import ConversionError, convert_html_to_epub
from html_to_epub_server.naming import PathTraversalError, render_filename, resolve_output_path

MAX_BODY_BYTES = 25 * 1024 * 1024

_ALLOWED_ORIGIN_PREFIXES = ("chrome-extension://", "safari-web-extension://")

logger = logging.getLogger(__name__)


class ConvertRequestHandler(BaseHTTPRequestHandler):
    """Handles /convert and /health. `config` is injected via `make_handler_class`."""

    config: ServerConfig
    server_version = f"html-to-epub-server/{__version__}"

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
        logger.info("%s - %s", self.address_string(), fmt % args)

    def _cors_origin(self) -> str | None:
        origin = self.headers.get("Origin")
        if origin and origin.startswith(_ALLOWED_ORIGIN_PREFIXES):
            return origin
        return None

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        origin = self._cors_origin()
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status: HTTPStatus, code: str, message: str) -> None:
        self._send_json(status, {"ok": False, "error": message, "code": code})

    def do_OPTIONS(self) -> None:  # noqa: N802 - stdlib naming
        if self.path != "/convert":
            self.send_response(HTTPStatus.NO_CONTENT)
            self.end_headers()
            return
        self.send_response(HTTPStatus.NO_CONTENT)
        origin = self._cors_origin()
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Auth-Token")
            self.send_header("Vary", "Origin")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802 - stdlib naming
        if self.path != "/health":
            self._error(HTTPStatus.NOT_FOUND, "bad_request", "unknown path")
            return
        self._send_json(HTTPStatus.OK, {"ok": True, "version": __version__})

    def do_POST(self) -> None:  # noqa: N802 - stdlib naming
        if self.path != "/convert":
            self._error(HTTPStatus.NOT_FOUND, "bad_request", "unknown path")
            return

        token = self.headers.get("X-Auth-Token", "")
        if not secrets.compare_digest(token, self.config.token):
            self._error(HTTPStatus.UNAUTHORIZED, "unauthorized", "missing or invalid X-Auth-Token")
            return

        content_length = self._parse_content_length()
        if content_length is None:
            self._error(HTTPStatus.BAD_REQUEST, "bad_request", "missing or invalid Content-Length")
            return
        if content_length > MAX_BODY_BYTES:
            self._error(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                "bad_request",
                f"request body exceeds {MAX_BODY_BYTES} bytes",
            )
            return

        raw_body = self.rfile.read(content_length)
        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError:
            self._error(HTTPStatus.BAD_REQUEST, "bad_request", "body is not valid JSON")
            return

        if not isinstance(payload, dict):
            self._error(HTTPStatus.BAD_REQUEST, "bad_request", "body must be a JSON object")
            return

        html = payload.get("html")
        url = payload.get("url")
        title = payload.get("title")
        raw_split_level = payload.get("split_level")
        split_level = self.config.split_level if raw_split_level is None else raw_split_level

        if not isinstance(html, str) or not html.strip():
            self._error(HTTPStatus.BAD_REQUEST, "no_content", "html is missing or blank")
            return
        if not isinstance(url, str) or not url.strip():
            self._error(HTTPStatus.BAD_REQUEST, "bad_request", "url is missing or blank")
            return
        if title is not None and not isinstance(title, str):
            self._error(HTTPStatus.BAD_REQUEST, "bad_request", "title must be a string or null")
            return
        if split_level not in (1, 2):
            self._error(HTTPStatus.BAD_REQUEST, "bad_request", "split_level must be 1 or 2")
            return

        try:
            filename = render_filename(self.config.filename_template, title=title, url=url)
            output_path = resolve_output_path(
                self.config.output_dir, filename, overwrite=self.config.overwrite
            )
            convert_html_to_epub(
                html=html,
                url=url,
                output_path=output_path,
                title=title,
                split_level=split_level,
                language=self.config.language,
            )
        except PathTraversalError as exc:
            self._error(HTTPStatus.BAD_REQUEST, "bad_request", str(exc))
            return
        except ConversionError as exc:
            self._error(HTTPStatus.BAD_REQUEST, "no_content", str(exc))
            return
        except OSError as exc:
            self._error(HTTPStatus.INTERNAL_SERVER_ERROR, "write_failed", str(exc))
            return

        self._send_json(HTTPStatus.OK, {"ok": True, "path": str(output_path)})

    def _parse_content_length(self) -> int | None:
        raw = self.headers.get("Content-Length")
        if raw is None:
            return None
        try:
            value = int(raw)
        except ValueError:
            return None
        return value if value >= 0 else None


def make_handler_class(config: ServerConfig) -> type[ConvertRequestHandler]:
    """Bind `config` onto a fresh handler subclass, as required by http.server's API."""
    return type("BoundConvertRequestHandler", (ConvertRequestHandler,), {"config": config})


def create_server(config: ServerConfig) -> ThreadingHTTPServer:
    """Build a ThreadingHTTPServer bound to 127.0.0.1 only -- never 0.0.0.0."""
    handler_cls: Callable[..., BaseHTTPRequestHandler] = make_handler_class(config)
    return ThreadingHTTPServer(("127.0.0.1", config.port), handler_cls)


__all__ = ["ConvertRequestHandler", "create_server", "make_handler_class"]
