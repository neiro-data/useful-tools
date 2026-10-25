# html-to-epub

## Resume

- **What it is:** a command line tool, `html2epub`. It reads clean HTML and writes a valid
  EPUB 3 file. The input is one HTML file, a directory of HTML files, or an `http(s)` address.
- **What it does:** it removes unsafe and decorative markup, splits the text into chapters at the
  headings, builds a nested table of contents (TOC), and writes the book. For a web address it
  first removes the page furniture (navigation, cookie banners, footers) and keeps the article.
- **Deterministic:** the same input and the same configuration always give the same output bytes.
- **Out of scope:** images, covers, JavaScript, CSS fidelity, and PDF input. The tool writes
  EPUB 3 only. It adds an NCX item as a fallback for old readers.
- **Stack:** Python 3.11 or later, a `uv` project, a `src/` layout. Runtime packages: `ebooklib`,
  `beautifulsoup4` with `lxml`, `httpx`, `trafilatura`. Development packages: `pytest`, `ruff`,
  `mypy` in strict mode.
- **Entry point:** `html2epub` maps to `html_to_epub.cli:main`.
- **Host requirements:** `uv`, and network access for a build from a web address. No database and
  no other service.

## Agent read
If you are an AI agent, read also [README_AGENT.md](README_AGENT.md).

## Quick start

```bash
uv sync                                                              # create .venv, install
uv run html2epub build tests/fixtures/single.html -o /tmp/out.epub   # one file
uv run html2epub build tests/fixtures/book/ -o /tmp/book.epub        # one chapter per file
uv run html2epub inspect tests/fixtures/single.html                  # print the derived tree
uv run html2epub validate /tmp/out.epub                              # check a written file
uv run pytest tests                                                  # 54 tests
```

For every other command and flag, see [scripts-guide.md](scripts-guide.md).

## Commands

The CLI has four sub-commands. Each one accepts a file, a directory, or a web address, except
`validate`, which reads a written `.epub` file.

| Command | What it does | Guide |
| --- | --- | --- |
| `build` | Writes one `.epub` file | [scripts-guide.md — Build](scripts-guide.md#build) |
| `fetch` | Saves the extracted article as HTML | [scripts-guide.md — Fetch, then build](scripts-guide.md#fetch-then-build) |
| `inspect` | Prints the chapters, the TOC, and the spine | [scripts-guide.md — Inspect and validate](scripts-guide.md#inspect-and-validate) |
| `validate` | Checks a written `.epub` file | [scripts-guide.md — Inspect and validate](scripts-guide.md#inspect-and-validate) |

Metadata comes from the CLI flags, a TOML sidecar, the page itself, or a fallback, in that order.
See [scripts-guide.md — Metadata](scripts-guide.md#metadata).

## Build from the web

Give `build` one address for one article, or `--url-list <file>` for one chapter per address. The
tool then fetches the pages and keeps the article text only.

Read the two limits before you trust the output. Article extraction is a heuristic: when it finds
no main content, the build uses the whole `<body>` and prints a `[warning]` line. URL safety is
scheme-only: the tool accepts `http` and `https` and rejects every other scheme, but it does not
block a private or internal address.

A build from a live address is not reproducible, because the page can change. Use `fetch` first
when you need the same bytes again. See
[scripts-guide.md — Build from the web](scripts-guide.md#build-from-the-web).

## Browser extension

`extension/` is a separate project. It holds a Chrome MV3 extension and a small local server. The
server reuses this package's pipeline, so no sanitize, split, or metadata logic is duplicated. One
click in the browser gives you the open page as an EPUB file.

The extension has its own `pyproject.toml`, its own lockfile, and its own documents. Run its
commands from `extension/`. See [extension/README.md](extension/README.md).

## Schema

The project uses no database. The two persistent formats are the `.epub` file and the `fetch`
output directory. The internal contract between the steps is the frozen dataclass set in
`models.py`.

[SCHEMA.md](SCHEMA.md) holds the pipeline shape, the book model, the sanitized element set, the
metadata precedence, the two output formats, and the validator checks.

## Layout

```
tool-html-to-epub/
├── README.md              this file: what it is, and the first run
├── README_AGENT.md        module map, design decisions, drift warnings
├── scripts-guide.md       every command and flag
├── SCHEMA.md              data contract, metadata rules, output formats
├── pyproject.toml         project, dependencies, ruff and mypy settings
├── uv.lock
├── src/html_to_epub/      12 modules, one per step of the pipeline
│   ├── __init__.py
│   ├── cli.py             argparse: build, fetch, inspect, validate
│   ├── config.py          BuildConfig
│   ├── epub_writer.py     the only module that imports ebooklib
│   ├── extract.py         the only module that imports trafilatura
│   ├── fetch.py           the only module that imports httpx
│   ├── loaders.py         read files and the TOML sidecar
│   ├── models.py          the internal contract
│   ├── normalize.py       sanitize to a well-formed XHTML fragment
│   ├── pipeline.py        load -> normalize -> structure -> BookModel
│   ├── structure.py       split into chapters, build the TOC
│   └── validator.py       model checks and written-file checks
├── tests/                 7 test modules, 54 tests, and fixtures/
└── extension/             separate project: Chrome MV3 extension + local server
```
