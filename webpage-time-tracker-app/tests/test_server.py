from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Iterator

import pytest

from config_gui import server, store
from config_gui.models import Config, Site


@pytest.fixture
def base_url() -> Iterator[str]:
    httpd, _thread = server.serve_forever_in_background(port=0)
    try:
        host, port = httpd.server_address[0], httpd.server_address[1]
        yield f"http://{host!s}:{port}"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_serves_the_stored_config(base_url: str) -> None:
    store.save(Config(sites=[Site.from_domain("Hacker News", "news.ycombinator.com", 20)]))
    with urllib.request.urlopen(f"{base_url}/config.json", timeout=5) as response:  # noqa: S310
        assert response.headers["Content-Type"] == "application/json"
        body = json.loads(response.read())
    assert body["sites"][0]["name"] == "Hacker News"
    assert Config.from_dict(body).sites[0].limit_minutes == 20


def test_binds_loopback_only(base_url: str) -> None:
    assert base_url.startswith("http://127.0.0.1:")


def test_other_paths_are_404(base_url: str) -> None:
    with pytest.raises(urllib.error.HTTPError) as caught:
        urllib.request.urlopen(f"{base_url}/state.json", timeout=5)  # noqa: S310
    assert caught.value.code == 404
