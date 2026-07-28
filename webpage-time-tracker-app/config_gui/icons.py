"""Favicons for the site list.

Each site's icon comes from that site's own `/favicon.ico`, fetched once and
cached as PNG under `~/.webpage-time-tracker/icons/`. No third-party icon
service is involved, and nothing is fetched again after the first success.
Anything that fails falls back to a drawn globe.

Icons are GUI-only. The in-page badge stays text, so the host page's CSP —
which blocks third-party images on exactly the sites being tracked — never
enters into it.
"""

from __future__ import annotations

import io
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw

from config_gui.store import icons_dir

ICON_SIZE = 20
FETCH_TIMEOUT_SECONDS = 3
MAX_ICON_BYTES = 200_000
_USER_AGENT = "webpage-time-tracker-config/0.2"


def icon_path(domain: str) -> Path:
    safe = "".join(char for char in domain if char.isalnum() or char in ".-") or "unknown"
    return icons_dir() / f"{safe}.png"


def globe_path() -> Path:
    """A drawn placeholder, so no binary asset has to live in the repo."""
    path = icons_dir() / "_globe.png"
    if not path.exists():
        image = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        box = (1, 1, ICON_SIZE - 2, ICON_SIZE - 2)
        draw.ellipse(box, outline=(120, 130, 145, 255), width=2)
        draw.ellipse(
            (ICON_SIZE // 2 - 3, 1, ICON_SIZE // 2 + 2, ICON_SIZE - 2), outline=(120, 130, 145, 255)
        )
        draw.line((1, ICON_SIZE // 2, ICON_SIZE - 2, ICON_SIZE // 2), fill=(120, 130, 145, 255))
        image.save(path, format="PNG")
    return path


def _download(domain: str) -> bytes:
    url = f"https://{domain}/favicon.ico"
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})  # noqa: S310
    # Scheme is fixed https above; the domain is validated as a hostname upstream.
    with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:  # noqa: S310
        return bytes(response.read(MAX_ICON_BYTES + 1))


def fetch(domain: str, *, force: bool = False) -> Path:
    """Path to this domain's cached icon, fetching it once; globe on any failure."""
    if not domain:
        return globe_path()
    cached = icon_path(domain)
    if cached.exists() and not force:
        return cached
    try:
        raw = _download(domain)
        if not raw or len(raw) > MAX_ICON_BYTES:
            return globe_path()
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
            image.convert("RGBA").resize((ICON_SIZE, ICON_SIZE), Image.Resampling.LANCZOS).save(
                cached, format="PNG"
            )
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return globe_path()
    return cached
