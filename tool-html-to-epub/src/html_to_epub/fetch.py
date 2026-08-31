"""Fetch a single web page over HTTP(S). Sole importer of httpx in this codebase."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

ALLOWED_SCHEMES = {"http", "https"}
MAX_BODY_BYTES = 10 * 1024 * 1024
MAX_REDIRECTS = 5
DEFAULT_USER_AGENT = "html2epub/0.1"


@dataclass(frozen=True)
class FetchedPage:
    """A downloaded page: the requested URL, the URL after redirects, and its HTML."""

    url: str
    final_url: str
    html: str


def fetch_url(url: str, *, timeout: float = 20.0, user_agent: str | None = None) -> FetchedPage:
    """Download `url` and return its HTML, following redirects.

    Raises ValueError on a disallowed scheme, non-2xx response, or an oversize body.
    """
    scheme = url.split("://", 1)[0].lower() if "://" in url else ""
    if scheme not in ALLOWED_SCHEMES:
        raise ValueError(f"unsupported URL scheme: {url}")

    headers = {"User-Agent": user_agent or DEFAULT_USER_AGENT}
    try:
        with httpx.Client(
            follow_redirects=True, max_redirects=MAX_REDIRECTS, timeout=timeout
        ) as client:
            with client.stream("GET", url, headers=headers) as response:
                if not response.is_success:
                    raise ValueError(f"fetch failed with status {response.status_code}: {url}")
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > MAX_BODY_BYTES:
                        raise ValueError(f"response body exceeds {MAX_BODY_BYTES} bytes: {url}")
                    chunks.append(chunk)
                final_url = str(response.url)
                final_scheme = response.url.scheme.lower()
                if final_scheme not in ALLOWED_SCHEMES:
                    # Defensive: httpx's transport mounting already blocks this in practice,
                    # but that's undocumented implementation behavior, not a contract.
                    raise ValueError(f"redirect escaped to unsupported scheme: {final_url}")
                encoding = response.encoding or "utf-8"
                html = b"".join(chunks).decode(encoding, errors="replace")
    except httpx.HTTPError as exc:
        raise ValueError(f"failed to fetch {url}: {exc}") from exc

    return FetchedPage(url=url, final_url=final_url, html=html)
