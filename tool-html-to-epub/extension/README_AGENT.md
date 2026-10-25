# README_AGENT

The HTTP contract, the module map, the security reasons, and the boundary with the parent project.
Referenced from [README.md](README.md).

A human who only wants to convert a page does not need this file.

## HTTP contract

Three routes exist. `handler.py` answers every other path with `404` and the body
`{"ok": false, "error": "unknown path", "code": "bad_request"}`.

Every answer is JSON. Every answer carries `Content-Type: application/json` and `Content-Length`.
An error answer always has the three keys `ok`, `error`, and `code`.

### `GET /health`

No header is necessary. No token is necessary.

```json
{"ok": true, "version": "0.1.0"}
```

The `version` value comes from `html_to_epub_server.__version__`.

### `POST /convert`

Headers: `Content-Type: application/json`, `X-Auth-Token: <token>`, and a valid `Content-Length`.

Request body:

| Field | Type | Rule |
| --- | --- | --- |
| `html` | string | Necessary. A blank string gives `400` with code `no_content`. |
| `url` | string | Necessary. A blank string gives `400` with code `bad_request`. |
| `title` | string or `null` | Optional. Another type gives `400`. |
| `split_level` | `1`, `2`, or `null` | `null` uses `split_level` from the config file. |

Success answer, status `200`:

```json
{"ok": true, "path": "/Users/you/Documents/html-to-epub-output/2026-09-02-title.epub"}
```

Failure answers:

| Status | `code` | Cause |
| --- | --- | --- |
| `401` | `unauthorized` | `X-Auth-Token` is absent or different from `token`. |
| `400` | `bad_request` | `Content-Length` is absent, not an integer, or negative. |
| `413` | `bad_request` | The body is larger than `MAX_BODY_BYTES` (25 MiB). |
| `400` | `bad_request` | The body is not valid JSON, or it is not a JSON object. |
| `400` | `bad_request` | A field has the wrong type, or `split_level` is not `1` or `2`. |
| `400` | `no_content` | `html` is blank, or the parent pipeline finds no content. |
| `400` | `bad_request` | `PathTraversalError`: the output path escapes `output_dir`. |
| `500` | `write_failed` | An `OSError` occurred during the write. |

The handler reads the token first. It reads the body length second. It reads the body last. A large
body from a caller with no token never reaches memory.

### `OPTIONS /convert`

The CORS preflight. It answers `204` with `Access-Control-Allow-Methods: POST, OPTIONS` and
`Access-Control-Allow-Headers: Content-Type, X-Auth-Token`. It sends those headers only when the
`Origin` header has an allowed prefix. `OPTIONS` on another path answers `204` with no CORS headers.

## Module map

`src/html_to_epub_server/` holds five modules and the package `__init__.py`.

| Module | Contents |
| --- | --- |
| `__init__.py` | `__version__ = "0.1.0"`. Nothing else. |
| `__main__.py` | `main()`. Loads the config, prints three lines, starts `serve_forever()`. |
| `config.py` | `ServerConfig` (frozen dataclass), `load_or_create_config`, `save_config`, `ConfigError`. |
| `convert.py` | `convert_html_to_epub`, `ConversionError`. The wrapper over the parent pipeline. |
| `handler.py` | `ConvertRequestHandler`, `make_handler_class`, `create_server`. |
| `naming.py` | `build_slug`, `render_filename`, `resolve_output_path`, `PathTraversalError`. |

`http.server` gives no way to pass state to a handler instance. `make_handler_class(config)` builds
a new subclass with `config` set as a class attribute. `create_server` uses that subclass.

The server is a `ThreadingHTTPServer`. One conversion does not block a `GET /health` call.

## Security design

The rules are in [README.md — Security](README.md#security). The reason for each rule follows.

- **The bind is `127.0.0.1`, never `0.0.0.0`.** The server writes files to disk on a command from a
  network client. A bind to `0.0.0.0` gives that command to every machine on the local network. The
  address is hard-coded in `create_server`, so the config file cannot change it. The port is
  configurable, but the interface is not.
- **`POST /convert` needs `X-Auth-Token`.** The loopback bind is not sufficient alone. Any local
  process, and any web page in the browser, can send a request to `127.0.0.1`. The token proves that
  the caller read the config file. The compare uses `secrets.compare_digest`, which takes the same
  time for each wrong value. A simple `==` compare leaks the correct prefix length through timing.
- **A body larger than 25 MiB gets `413`.** The handler reads the full body into memory. Without a
  limit, one request can use all available memory and stop the machine. The limit is read from the
  `Content-Length` header before the read, so the large body is refused, not buffered.
- **CORS matches a scheme prefix, not an identifier.** The Safari extension identifier is different
  on each machine, so a fixed allowlist cannot work. The prefixes `chrome-extension://` and
  `safari-web-extension://` cannot come from a normal web page: the browser sets the `Origin` header,
  and a page on `http://` or `https://` cannot claim an extension scheme. The answer echoes the
  origin and adds `Vary: Origin`, so a cache does not give one origin the header of another.
- **The write stays inside `output_dir`.** The filename comes from a caller-controlled `title`. The
  guard has two parts. `resolve_output_path` keeps the basename only, so `../../etc/passwd` becomes
  `passwd`. Then `_assert_within` compares the resolved path against the resolved base folder, which
  catches a symlink that points out of the folder. The same check runs again on each `-2`, `-3`
  collision candidate.

## Boundary with the parent project

This package holds no sanitize, split, table-of-contents, or metadata logic. The parent
`html_to_epub` package holds all of it. `pyproject.toml` declares the parent as an editable path
dependency: `html-to-epub = { path = "..", editable = true }`.

Two modules import from the parent, not one:

| Module | Imports from the parent |
| --- | --- |
| `convert.py` | `html_to_epub.config.BuildConfig`, `html_to_epub.epub_writer.write_epub`, `html_to_epub.pipeline.build_book_model_from_html`, `html_to_epub.validator.validate_model` |
| `naming.py` | `html_to_epub.pipeline.slugify_url` |

`convert.py` is the only wrapper over the build, validate, and write pipeline. That is the claim in
its own docstring, and it is correct. `naming.py` reuses one helper, `slugify_url`, to give the
filename slug the same shape as the parent gives it. Keep that boundary: a change to the conversion
behaviour belongs in the parent, in [../README.md](../README.md).

`convert.py` builds a `BuildConfig` with `input_path=None` and `metadata_path=None`, because the
HTML arrives in memory from the browser. It sends `urls=(url,)` so the parent can resolve relative
links. It runs `validate_model` and raises `ConversionError` when a finding has `level == "error"`.
A warning-level finding does not stop the write.

## The port in three places

The port `8765` is hard-coded in three files. A change to one alone breaks the extension without an
error message.

| File | Item | Value |
| --- | --- | --- |
| `~/.config/html-to-epub-extension/config.json` | `port` | `8765` |
| `chrome/popup.js` | `SERVER_ORIGIN` | `http://127.0.0.1:8765` |
| `chrome/manifest.json` | `host_permissions` | `http://127.0.0.1:8765/*` |

`config.py` also holds `DEFAULT_PORT = 8765`, which is the value written into a new config file.

A wrong `host_permissions` value gives a CORS failure in the popup, not a clear error. A wrong
`SERVER_ORIGIN` value gives the "Server unreachable" message. The config value `0` lets the
operating system select a port; that mode is for a test, because the extension cannot follow it.

## Docs map

| File | Contents |
| --- | --- |
| [README.md](README.md) | What the extension is, the quick start, the popup, the config, the security rules. |
| [README_AGENT.md](README_AGENT.md) | This file. The HTTP contract, the module map, the design reasons. |
| [scripts-guide.md](scripts-guide.md) | Every command: the server, the extension reload, the checks, the Safari build. |
| [MANUAL-TESTS.md](MANUAL-TESTS.md) | The browser checks that `pytest` cannot do. |
