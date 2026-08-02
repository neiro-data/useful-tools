# html-to-epub

Convert clean HTML (one file, or a directory of files) into a valid, deterministic EPUB 3.
Text-first: v1 explicitly excludes images, covers, JavaScript, CSS fidelity, EPUB 2/NCX, and PDF.

## Resume

- **What it is:** a CLI, `html2epub`, that sanitizes HTML, splits it into chapters at headings,
  builds a nested TOC, and writes a byte-deterministic `.epub` file. Same input + config always
  produces the same output bytes.
- **Stack:** Python 3.11+, `uv` project, `src/` layout. Runtime deps: `ebooklib`, `beautifulsoup4`
  (with `lxml`). Dev: `pytest`, `ruff`, `mypy` (strict).
- **How to run:**
  ```bash
  uv sync
  uv run html2epub build <input.html|dir> -o out.epub
  uv run html2epub inspect <input.html|dir>
  uv run html2epub validate out.epub
  ```

## Setup

```bash
uv sync
```

## Usage

```bash
# Build from a single HTML file
uv run html2epub build tests/fixtures/single.html -o /tmp/out.epub

# Build from a directory of HTML files (one chapter per file, sorted by filename)
uv run html2epub build tests/fixtures/book/ -o /tmp/book.epub

# Override / supply metadata (CLI flags > TOML sidecar > scraped <title>/<meta>)
uv run html2epub build input.html -o out.epub \
  --title "My Book" --author "Jane Doe" --language en \
  --metadata meta.toml

# Split chapters on <h1> only (default) or <h1>+<h2>
uv run html2epub build input.html -o out.epub --split-level 2

# Inspect the derived chapter/TOC/spine tree without writing anything
uv run html2epub inspect input.html

# Validate a written EPUB
uv run html2epub validate out.epub
```

## Design notes

- `models.py` is the hard internal boundary: parsing and chapter-splitting logic never see
  `ebooklib` types. Only `epub_writer.py` imports `ebooklib`.
- `normalize.py` guarantees its output always parses with `xml.etree.ElementTree` — malformed
  XHTML is the most common reason e-readers reject a book.
- Determinism: content hashing (BLAKE2b) replaces `uuid4()`/`datetime.now()` when no explicit
  identifier/date is given; the written zip has fixed entry timestamps, sorted order, and
  `mimetype` stored first and uncompressed.

## Tests

```bash
uv run pytest
uv run ruff check .
uv run mypy
```
