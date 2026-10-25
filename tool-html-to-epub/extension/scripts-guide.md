# scripts-guide

Every command of the extension sub-project, grouped by target.
Referenced from [README.md](README.md).

Run each command from the `extension/` folder. The `uv run` prefix uses the project `.venv`.

## Server

`html2epub-server` is the only entry point. `pyproject.toml` maps it to
`html_to_epub_server.__main__:main`.

```bash
uv sync                                     # create .venv and install the dev group
uv run html2epub-server                     # start the server on 127.0.0.1
uv run python -m html_to_epub_server        # the same start, through the module
```

The server prints three lines at start: the config path, the port, and the output folder. It runs
until you stop it with `Ctrl+C`.

The first start creates `~/.config/html-to-epub-extension/config.json`. Read the `token` field from
that file. The extension needs that value.

```bash
cat ~/.config/html-to-epub-extension/config.json                    # show the full config
python3 -c "import json,pathlib;print(json.loads(pathlib.Path.home().joinpath('.config/html-to-epub-extension/config.json').read_text())['token'])"   # show the token only
```

To test the server without the extension, call the two routes with `curl`. Replace `<token>` with
the value from the config file.

```bash
curl http://127.0.0.1:8765/health                                   # -> {"ok": true, "version": "0.1.0"}
curl -X POST http://127.0.0.1:8765/convert \
  -H 'Content-Type: application/json' \
  -H 'X-Auth-Token: <token>' \
  -d '{"html":"<h1>Title</h1><p>Body</p>","url":"https://example.com","title":"Title","split_level":null}'
```

A correct `POST /convert` answers `{"ok": true, "path": "<file>"}`. For the full contract, see
[README_AGENT.md — HTTP contract](README_AGENT.md#http-contract).

## Chrome extension

The extension is unpacked. Chrome loads it from the folder, so there is no build step and no
bundler.

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Click **Load unpacked**. Select `extension/chrome/`.
4. Click the toolbar icon. Put the token in the **Auth token** field. Click **Save**.

After each edit of `chrome/popup.js`, `chrome/capture.js`, `chrome/popup.html`, `chrome/popup.css`,
or `chrome/manifest.json`, click the reload arrow on the extension card in `chrome://extensions`.
Then close and open the popup again. A `manifest.json` edit always needs the reload.

To read the popup errors, right-click the popup and select **Inspect**. The popup has its own
DevTools console. This build has no background service worker, so there is no second console.

## Development

`pyproject.toml` configures `ruff` (line length 100, rules `E`, `F`, `I`, `W`, `UP`, `S`, `B`) and
`mypy` (`strict = true`, `files = ["src", "tests"]`). The dev group holds `mypy`, `pytest`, `ruff`,
and `httpx`.

```bash
uv run pytest -q                            # 25 tests, all pass
uv run ruff check .                         # lint
uv run ruff format .                        # format, quote-style double
uv run ruff format --check .                # format check only, 11 files
uv run mypy                                 # strict check of src and tests
```

The tests are `tests/test_config.py` (5 tests), `tests/test_naming.py` (10 tests), and
`tests/test_server.py` (10 tests). `test_server.py` starts a real server on port `0` and calls it
with `httpx`.

The parent project is an editable dependency (`html-to-epub = { path = "..", editable = true }`).
An edit in the parent `src/` applies immediately. No reinstall is necessary.

## Manual browser checks

`pytest` cannot load an extension in a browser. The checks that need a browser are in
[MANUAL-TESTS.md](MANUAL-TESTS.md). Start the server before you do them.

The list has three groups: the Chrome checks, the Safari checks, and the items that do not apply to
this build. Do the Chrome group after each change to `chrome/`.

## Safari build

**The Safari build does not exist in this repository.** There is no `extension/safari/` folder, no
Xcode project, and no build command for Safari. Do not look for one.

The server is ready for Safari. `handler.py` accepts a Cross-Origin Resource Sharing (CORS) origin
that starts with `chrome-extension://` or `safari-web-extension://`. It uses no fixed extension
identifier, because the Safari identifier changes for each machine. See
[README.md — Security](README.md#security).

To make the Safari build, a machine needs these items:

- A full Xcode installation. Command Line Tools alone are not sufficient.
- The `xcrun safari-web-extension-converter` tool, which comes with Xcode.
- A signing identity, or the **Develop → Allow Unsigned Extensions** setting in Safari. That setting
  goes back to off after each Safari restart.

The command below is the documented converter call. It is not verified in this repository, because
this environment has Command Line Tools only.

```bash
xcrun safari-web-extension-converter extension/chrome/ \
  --macos-only \
  --project-location extension/safari/          # NOT RUN HERE: needs full Xcode
```

After a successful conversion, do the Safari checks in
[MANUAL-TESTS.md](MANUAL-TESTS.md). The first request to `127.0.0.1` shows the macOS **Local
Network** permission prompt.
