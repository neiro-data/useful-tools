"""Loopback config server.

The userscript can't read a file off disk, so the GUI publishes the config over
HTTP while its window is open. Bound to 127.0.0.1 only — this is never reachable
from another machine, and there is no separate daemon to manage.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from config_gui import store

HOST = "127.0.0.1"
PORT = 8787
CONFIG_URL = f"http://{HOST}:{PORT}/config.json"


class _Handler(BaseHTTPRequestHandler):
    server_version = "wtt-config"

    def do_GET(self) -> None:  # noqa: N802 — BaseHTTPRequestHandler's naming
        if self.path.split("?")[0] != "/config.json":
            self.send_error(404, "not found")
            return
        body = json.dumps(store.load().to_dict()).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        """Silence the per-request stderr log — this runs behind a GUI."""


def serve_forever_in_background(port: int = PORT) -> tuple[ThreadingHTTPServer, threading.Thread]:
    """Start the server on a daemon thread. `port=0` picks a free one (tests)."""
    httpd = ThreadingHTTPServer((HOST, port), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, name="wtt-config-server", daemon=True)
    thread.start()
    return httpd, thread
