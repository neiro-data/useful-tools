from __future__ import annotations

import threading
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from html_to_epub_server.config import ServerConfig
from html_to_epub_server.handler import create_server

TOKEN = "test-token"

_SAMPLE_HTML = "<html><body><h1>Title</h1><p>Some content for the article.</p></body></html>"


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    d = tmp_path / "out"
    d.mkdir()
    return d


@pytest.fixture
def base_config(output_dir: Path) -> ServerConfig:
    return ServerConfig(output_dir=str(output_dir), port=0, token=TOKEN)


@pytest.fixture
def running_server(base_config: ServerConfig) -> Iterator[tuple[str, ServerConfig]]:
    server = create_server(base_config)
    actual_port = server.server_address[1]
    config = replace(base_config, port=actual_port)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{actual_port}", config
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_health_ok(running_server: tuple[str, ServerConfig]) -> None:
    base_url, _ = running_server
    resp = httpx.get(f"{base_url}/health", timeout=5)
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_convert_happy_path(running_server: tuple[str, ServerConfig], output_dir: Path) -> None:
    base_url, _ = running_server
    resp = httpx.post(
        f"{base_url}/convert",
        json={"html": _SAMPLE_HTML, "url": "https://example.com/article", "title": "My Article"},
        headers={"X-Auth-Token": TOKEN},
        timeout=10,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    written = Path(body["path"])
    assert written.exists()
    assert written.parent == output_dir.resolve()


def test_convert_missing_html_is_bad_request(running_server: tuple[str, ServerConfig]) -> None:
    base_url, _ = running_server
    resp = httpx.post(
        f"{base_url}/convert",
        json={"html": "", "url": "https://example.com"},
        headers={"X-Auth-Token": TOKEN},
        timeout=5,
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "no_content"


def test_convert_wrong_token_is_unauthorized(running_server: tuple[str, ServerConfig]) -> None:
    base_url, _ = running_server
    resp = httpx.post(
        f"{base_url}/convert",
        json={"html": _SAMPLE_HTML, "url": "https://example.com"},
        headers={"X-Auth-Token": "wrong"},
        timeout=5,
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == "unauthorized"


def test_convert_missing_token_is_unauthorized(running_server: tuple[str, ServerConfig]) -> None:
    base_url, _ = running_server
    resp = httpx.post(
        f"{base_url}/convert",
        json={"html": _SAMPLE_HTML, "url": "https://example.com"},
        timeout=5,
    )
    assert resp.status_code == 401


def test_convert_oversized_body_is_413(running_server: tuple[str, ServerConfig]) -> None:
    base_url, _ = running_server
    huge_body = b'{"html": "' + (b"a" * (26 * 1024 * 1024)) + b'", "url": "https://x.com"}'
    resp = httpx.post(
        f"{base_url}/convert",
        content=huge_body,
        headers={"X-Auth-Token": TOKEN, "Content-Type": "application/json"},
        timeout=15,
    )
    assert resp.status_code == 413


def test_convert_unwritable_output_dir_is_write_failed(output_dir: Path) -> None:
    config = ServerConfig(output_dir=str(output_dir), port=0, token=TOKEN)
    server = create_server(config)
    actual_port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        output_dir.chmod(0o400)
        resp = httpx.post(
            f"http://127.0.0.1:{actual_port}/convert",
            json={"html": _SAMPLE_HTML, "url": "https://example.com"},
            headers={"X-Auth-Token": TOKEN},
            timeout=10,
        )
        assert resp.status_code == 500
        assert resp.json()["code"] == "write_failed"
    finally:
        output_dir.chmod(0o700)
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_convert_collision_appends_suffix(
    running_server: tuple[str, ServerConfig], output_dir: Path
) -> None:
    base_url, _ = running_server
    payload = {"html": _SAMPLE_HTML, "url": "https://example.com/article", "title": "Collide"}

    first = httpx.post(
        f"{base_url}/convert", json=payload, headers={"X-Auth-Token": TOKEN}, timeout=10
    )
    second = httpx.post(
        f"{base_url}/convert", json=payload, headers={"X-Auth-Token": TOKEN}, timeout=10
    )

    assert first.json()["path"] != second.json()["path"]
    assert Path(second.json()["path"]).name.endswith("-2.epub")


def test_convert_cors_preflight(running_server: tuple[str, ServerConfig]) -> None:
    base_url, _ = running_server
    resp = httpx.request(
        "OPTIONS",
        f"{base_url}/convert",
        headers={"Origin": "chrome-extension://abcdefgh"},
        timeout=5,
    )
    assert resp.status_code == 204
    assert resp.headers["Access-Control-Allow-Origin"] == "chrome-extension://abcdefgh"


def test_convert_cors_rejects_untrusted_origin(running_server: tuple[str, ServerConfig]) -> None:
    base_url, _ = running_server
    resp = httpx.request(
        "OPTIONS",
        f"{base_url}/convert",
        headers={"Origin": "https://evil.example.com"},
        timeout=5,
    )
    assert "Access-Control-Allow-Origin" not in resp.headers
