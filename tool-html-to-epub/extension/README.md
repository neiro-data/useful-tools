# html-to-epub browser extension

## Resume

- **Stack:** Python 3.11+ / `uv` local loopback server (`html_to_epub_server`, stdlib `http.server`)
  + a Chrome MV3 extension (`extension/chrome/`, popup-only, no background service worker). Safari
  build not yet generated in this repo (see below).
- **Run the server:** `cd extension && uv sync && uv run html2epub-server`
- **Load the extension:** chrome://extensions → Developer mode → Load unpacked → `extension/chrome/`.
- **Tests/lint:** `uv run pytest -q`, `uv run ruff check .`, `uv run mypy --strict src` (all from
  `extension/`).

## Setup

```bash
cd extension
uv sync
uv run html2epub-server
```

On first run the server creates `~/.config/html-to-epub-extension/config.json` with defaults and a
generated `token`, and prints the config path, port, and output folder to stdout. Copy the `token`
value from that file into the extension popup (the popup has a token field and a "save" button; the
token is stored via `chrome.storage.local`).

The server binds to `127.0.0.1` only, on port `8765` by default (configurable in `config.json`).

## Loading the unpacked extension in Chrome

1. Open `chrome://extensions`.
2. Enable **Developer mode** (top right).
3. Click **Load unpacked** and select `extension/chrome/`.
4. Pin the extension icon to the toolbar if you want quick access.

## Usage

1. Make sure the server is running (`uv run html2epub-server`).
2. Navigate to the page you want to convert.
3. Click the toolbar icon to open the popup. It shows server health (via `GET /health`).
4. If the token hasn't been saved yet, paste it and click "Save".
5. Click **Convert this page**. The popup captures the rendered DOM of the active tab, POSTs it to
   the server, and shows either the saved `.epub` path or an error message inline in the popup.

There is no badge or OS notification in this build — status is shown entirely in the popup, and the
popup must stay open for the duration of the conversion.

## Safari

**Not built in this repo.** The Safari conversion step requires the full Xcode toolchain
(`xcrun safari-web-extension-converter`), which is not available in this environment (only Command
Line Tools are installed). On a machine with full Xcode installed, run:

```bash
xcrun safari-web-extension-converter extension/chrome/ --macos-only --project-location extension/safari/
```

Commit the generated Xcode project under `extension/safari/` once built, and re-run the same command
to regenerate it after changes to `extension/chrome/`. See `extension/MANUAL-TESTS.md` for the
Safari-specific manual checklist (Local Network permission prompt, unsigned-extension allowance,
etc.) once that build exists.

## Security notes

- The server binds to `127.0.0.1` only — never `0.0.0.0`.
- All `/convert` requests require a shared token (`X-Auth-Token` header) matching the value in
  `config.json`. Requests without a valid token are rejected with `401`.
- CORS is restricted by `Origin` scheme prefix (`chrome-extension://`, `safari-web-extension://`),
  not a hardcoded extension ID, since the Safari extension ID varies per machine. See
  `extension/src/html_to_epub_server/handler.py`.
