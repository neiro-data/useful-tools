"""Regression tests for SQLite thread-affinity under a real uvicorn server.

``fastapi.testclient.TestClient`` runs an entire request inside a single "portal" thread, so it
can never reproduce the bug this module guards against: ``sqlite3.connect()`` without
``check_same_thread=False`` raises ``sqlite3.ProgrammingError`` as soon as a connection created on
one worker thread is used by another. Under real uvicorn, concurrent requests are dispatched
across a threadpool, so that failure mode only shows up when the app is actually served over HTTP
with genuine concurrency.

These tests launch the app as a subprocess (``uvicorn`` on an ephemeral port, pointed at a
temporary SQLite file), then hammer it with concurrent requests via a thread pool.
"""

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

pytestmark = pytest.mark.slow


def _free_port() -> int:
    """Return an ephemeral TCP port that is currently unused."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_health(
    base_url: str, process: subprocess.Popen[bytes], log_path: Path, timeout: float = 10.0
) -> None:
    """Poll ``/health`` until it responds or the timeout elapses.

    Raises if the server process exits early, so a startup crash fails fast with a clear message
    instead of spinning until the timeout. The server's captured output is included in the error
    so a failure here is diagnosable.
    """
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"uvicorn subprocess exited early with code {process.returncode!r}\n"
                f"server output:\n{log_path.read_text()}"
            )
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=1) as response:  # noqa: S310
                if response.status == 200:
                    return
        except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
            last_error = exc
        time.sleep(0.05)
    raise TimeoutError(
        f"server did not become healthy within {timeout}s (last error: {last_error})"
    )


@pytest.fixture
def live_server(tmp_path: Path) -> Iterator[str]:
    """Launch the real app under uvicorn in a subprocess, against a fresh temp SQLite file.

    Yields the server's base URL. The subprocess is terminated (and killed if it doesn't exit
    promptly) in a ``finally`` block, so it is torn down even if a test fails or raises.
    """
    db_path = tmp_path / "live_server.db"
    log_path = tmp_path / "uvicorn.log"
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"

    env = {**os.environ, "TIME_TRACKER_DATABASE_PATH": str(db_path)}

    # Server output goes to a file rather than a pipe: nothing in this fixture drains the pipe, so
    # a chatty server could fill the OS buffer and deadlock the child on write (and us on wait()).
    with log_path.open("wb") as log_file:
        process = subprocess.Popen(  # noqa: S603
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
    try:
        _wait_for_health(base_url, process, log_path)
        yield base_url
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def test_concurrent_reads_all_succeed(live_server: str) -> None:
    """~30 concurrent ``GET /tags`` requests against a real server should all return 200.

    Before the fix (default ``check_same_thread=True``), uvicorn's threadpool dispatch caused
    the majority of these requests to fail with ``sqlite3.ProgrammingError``.
    """

    def get_tags(_index: int) -> int:
        with urllib.request.urlopen(f"{live_server}/tags", timeout=5) as response:  # noqa: S310
            return response.status

    with ThreadPoolExecutor(max_workers=30) as pool:
        statuses = list(pool.map(get_tags, range(30)))

    assert statuses == [200] * 30


def test_concurrent_read_write_all_succeed(live_server: str) -> None:
    """Mixed concurrent ``POST /tags`` and ``GET /today`` requests should all succeed.

    This exercises the busy-timeout/WAL path added alongside ``check_same_thread=False``: without
    a busy timeout, a writer holding the SQLite lock can cause concurrent readers/writers to raise
    ``sqlite3.OperationalError: database is locked`` instead of retrying briefly.
    """

    def post_tag(index: int) -> int:
        body = f'{{"name": "concurrent-tag-{index}"}}'.encode()
        request = urllib.request.Request(  # noqa: S310
            f"{live_server}/tags",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310
                return response.status
        except urllib.error.HTTPError as exc:
            return exc.code

    def get_today(_index: int) -> int:
        with urllib.request.urlopen(f"{live_server}/today", timeout=5) as response:  # noqa: S310
            return response.status

    with ThreadPoolExecutor(max_workers=30) as pool:
        write_futures = [pool.submit(post_tag, i) for i in range(15)]
        read_futures = [pool.submit(get_today, i) for i in range(15)]
        write_statuses = [future.result() for future in write_futures]
        read_statuses = [future.result() for future in read_futures]

    # Writes may 201 (created) or 409 (duplicate name race), but never fail with a server error.
    assert all(status in (201, 409) for status in write_statuses)
    assert read_statuses == [200] * 15
