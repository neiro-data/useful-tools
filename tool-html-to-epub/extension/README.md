# html-to-epub browser extension

## Resume

- **What it is:** a Chrome extension and a local server. The extension captures the rendered DOM of
  the open tab. The server converts that HTML into an EPUB 3 file and writes it to disk.
- **Stack:** Python 3.11 or later, `uv`, `src/` layout, the standard-library `http.server`. The
  extension is Manifest V3 (MV3), popup-only, with no background service worker.
- **Entry point:** `uv run html2epub-server`, the `html2epub-server` script in `pyproject.toml`.
- **Host requirements:** `uv`, Python 3.11 or later, and Chrome. The server listens on `127.0.0.1`
  only, on port `8765` by default.
- **Parent project:** this sub-project reuses the conversion pipeline of `html-to-epub`. It holds no
  sanitize, split, or metadata logic of its own. See [../README.md](../README.md).
- **Safari:** the Safari build does not exist in this repository. See
  [scripts-guide.md — Safari build](scripts-guide.md#safari-build).

## Agent read
If you are an AI agent, read also [README_AGENT.md](README_AGENT.md).

## Quick start

1. Start the server:
   ```bash
   cd extension
   uv sync
   uv run html2epub-server
   ```
   The first run creates `~/.config/html-to-epub-extension/config.json`. The server prints the
   config path, the port, and the output folder.
2. Open that config file. Copy the value of `token`.
3. Open `chrome://extensions`. Enable **Developer mode**.
4. Click **Load unpacked**. Select the `extension/chrome/` folder.
5. Click the toolbar icon. Paste the token into the **Auth token** field. Click **Save**.
6. Open the page to convert. Click the toolbar icon. Click **Convert this page**.

The popup shows the path of the saved `.epub` file. For every other command, see
[scripts-guide.md](scripts-guide.md).

## Popup

The popup is the complete user interface. It holds a server status line, an auth token field, and
the **Convert this page** button. The popup calls `GET /health` when it opens. It keeps the button
disabled while the server does not answer.

Keep the popup open until the conversion ends. This build has no toolbar badge and no operating
system notification. The popup shows every result and every error.

| Popup message | Meaning |
| --- | --- |
| `Server running (v0.1.0).` | The server answered `GET /health`. |
| `Server unreachable. Start it with: uv run html2epub-server` | The server is stopped, or the port differs. |
| `Set the auth token first.` | The extension holds no saved token. |
| `Saved: <path>` | The server wrote the EPUB file. |

## Configuration

The server reads `~/.config/html-to-epub-extension/config.json`. It creates that file with the
defaults below on the first run. It rejects an unknown field with an error, so a typo fails early.
Restart the server after each edit.

| Field | Default | Purpose |
| --- | --- | --- |
| `output_dir` | `~/Documents/html-to-epub-output` | The folder for the `.epub` files. |
| `port` | `8765` | The loopback port. `0` lets the operating system select a port. |
| `token` | generated | The shared secret for the `X-Auth-Token` header. |
| `split_level` | `1` | Split chapters at `<h1>` (`1`), or at `<h1>` and `<h2>` (`2`). |
| `language` | `en` | The language in the EPUB metadata. |
| `filename_template` | `{date}-{slug}.epub` | The name template. It accepts `{date}` and `{slug}` only. |
| `overwrite` | `false` | Replace an existing file. `false` appends `-2`, `-3`, and so on. |

The extension holds the port in two more places: the `SERVER_ORIGIN` constant in `chrome/popup.js`,
and `host_permissions` in `chrome/manifest.json`. Change those two files also if you change `port`.

## Security

- The server binds to `127.0.0.1`. It never binds to `0.0.0.0`.
- Every `POST /convert` request must carry the `X-Auth-Token` header. The value must match `token`
  in the config file. The server answers `401` to every other value.
- The server accepts a request body of 25 MiB or less. A larger body gets `413`.
- The server accepts a Cross-Origin Resource Sharing (CORS) origin by scheme prefix:
  `chrome-extension://` or `safari-web-extension://`. It uses no fixed extension identifier, because
  the Safari identifier changes for each machine.
- The server writes only inside `output_dir`. It rejects a path that escapes that folder.

For the reason behind each rule, see
[README_AGENT.md — Security design](README_AGENT.md#security-design).

## Layout

```text
extension/
├── README.md            This file. What it is, how to run it.
├── README_AGENT.md      The HTTP contract, the boundaries, the design decisions.
├── scripts-guide.md     Every command, grouped by target.
├── MANUAL-TESTS.md      The browser checks that pytest cannot do.
├── pyproject.toml       The manifest, the entry point, the ruff and mypy settings.
├── uv.lock
├── chrome/              The MV3 extension.
│   ├── manifest.json
│   ├── popup.html       The popup markup.
│   ├── popup.css
│   ├── popup.js         The status, token, and convert logic.
│   ├── capture.js       The function injected into the page.
│   └── icons/           icon16.png, icon48.png, icon128.png
├── src/html_to_epub_server/
│   ├── __main__.py      The `html2epub-server` entry point.
│   ├── config.py        Load or create config.json.
│   ├── convert.py       The only wrapper over the parent pipeline.
│   ├── handler.py       The HTTP server and the request handler.
│   └── naming.py        The filename template and the path guard.
└── tests/               test_config.py, test_naming.py, test_server.py
```
