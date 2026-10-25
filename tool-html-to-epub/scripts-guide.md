# scripts-guide

Every command of the `html2epub` command line interface (CLI), and the development tasks.
Referenced from [README.md](README.md).

Run each command from the project root. The `uv run` prefix uses the project `.venv`.

## Build

`build` writes one `.epub` file. It needs an output path.

```bash
uv run html2epub build tests/fixtures/single.html -o /tmp/out.epub   # one HTML file
uv run html2epub build tests/fixtures/book/ -o /tmp/book.epub        # one chapter per file
uv run html2epub build input.html -o out.epub --split-level 2        # split at <h1> and <h2>
```

A directory build reads only `.html` and `.xhtml` files. It sorts them by filename. An empty
directory is an error.

`--split-level` accepts `1` or `2`. The default is `1`.

## Metadata

The CLI flags have the highest precedence. See
[SCHEMA.md — Metadata precedence](SCHEMA.md#metadata-precedence) for the full order.

```bash
uv run html2epub build input.html -o out.epub \
  --title "My Book" \
  --author "Jane Doe" \
  --language en \
  --identifier "urn:uuid:my-book-001" \
  --metadata meta.toml
```

`--metadata` reads a TOML sidecar. See
[SCHEMA.md — TOML metadata sidecar](SCHEMA.md#toml-metadata-sidecar) for the accepted keys.

## Build from the web

Read the two warnings below before you build from a URL.

- Article extraction is a heuristic. When it finds no main content, the build uses the whole
  `<body>` instead. It then prints a `[warning]` line. The book still builds. That chapter
  contains page furniture. Read the warning before you trust the output.
- URL safety is scheme-only. The tool accepts `http` and `https`. It rejects every other scheme,
  and it checks the scheme again after each redirect. There is no guard against a URL that points
  at a private or internal address. See
  [README_AGENT.md — Extraction limits](README_AGENT.md#extraction-limits).

```bash
uv run html2epub build https://example.com/article -o out.epub      # one URL, one article
uv run html2epub build --url-list urls.txt -o out.epub              # one chapter per URL
uv run html2epub build <url> -o out.epub --timeout 30               # network timeout, seconds
uv run html2epub build <url> -o out.epub --user-agent "my-reader/1.0"
```

A `--url-list` file holds one URL per line. The reader ignores blank lines and `#` comments.

Do not combine a positional input path with `--url-list`. The CLI rejects that combination with an
error. It does not drop one of the two.

`--timeout` defaults to 20 seconds.

## Fetch, then build

A direct URL build is only as reproducible as the page behind the URL. The site can change its
content or its markup. Two builds of the same URL can produce different bytes.

Use two steps when you need reproducible output. `fetch` makes the network step explicit.

```bash
uv run html2epub fetch https://example.com/article -o pages/   # one URL
uv run html2epub fetch --url-list urls.txt -o pages/           # many URLs
uv run html2epub build pages/ -o out.epub                      # deterministic, and offline
```

`fetch` writes the extracted article, not the raw page. It names each file `NNNN-<slug>.html`. The
number keeps the directory in reading order. See
[SCHEMA.md — Fetch output format](SCHEMA.md#fetch-output-format).

Everything after the fetch is byte-deterministic. Keep `pages/` if you want to rebuild the same
book later.

## Inspect and validate

`inspect` prints the derived chapters, the table of contents (TOC), and the spine. It writes no
file. It accepts the same input forms and the same `--metadata`, `--split-level`, `--url-list`,
`--timeout` and `--user-agent` flags as `build`.

```bash
uv run html2epub inspect input.html
uv run html2epub inspect https://example.com/article
uv run html2epub validate out.epub
```

`validate` reads a written `.epub` file. It prints one `[error]` or `[warning]` line per finding.
It prints `<path>: valid` and exits `0` when it finds no error. It exits `1` on any error.

## Browser extension server

`extension/` is a separate project with its own `pyproject.toml` and its own lockfile. Run its
commands from `extension/`.

```bash
cd extension
uv sync
uv run html2epub-server
```

See [extension/README.md](extension/README.md) for the token setup, the Chrome load steps, and the
Safari status.

## Development

```bash
uv sync                  # create .venv and install the runtime and dev dependencies
uv run pytest tests      # run the 54 tests in tests/
uv run ruff check .      # lint
uv run ruff format .     # format
uv run mypy              # type check src/ and tests/ in strict mode
```

Give `pytest` the `tests` path. Without it, pytest also collects `extension/tests/`, which needs
the extension environment, and the run stops with 3 collection errors. See
[README_AGENT.md — Drift warnings](README_AGENT.md#drift-warnings).

`uv run mypy` needs no path argument. `pyproject.toml` sets `files = ["src", "tests"]`. It checks
19 source files.

Add a dependency with `uv add <package>`. Add a development dependency with `uv add --dev
<package>`. Do not edit `pyproject.toml` by hand.
