# html-to-epub

Convert clean HTML (one file, a directory of files, or a web URL) into a valid, deterministic
EPUB 3. Text-first: explicitly excludes images, covers, JavaScript, CSS fidelity, EPUB 2/NCX, and PDF.

## Resume

- **What it is:** a CLI, `html2epub`, that sanitizes HTML, splits it into chapters at headings,
  builds a nested TOC, and writes a byte-deterministic `.epub` file. Same input + config always
  produces the same output bytes. It also takes `http(s)` URLs directly, stripping page furniture
  (nav, cookie banners, footers) down to the article itself.
- **Stack:** Python 3.11+, `uv` project, `src/` layout. Runtime deps: `ebooklib`, `beautifulsoup4`
  (with `lxml`), `httpx` (fetch), `trafilatura` (article extraction). Dev: `pytest`, `ruff`,
  `mypy` (strict).
- **How to run:**
  ```bash
  uv sync
  uv run html2epub build <input.html|dir|url> -o out.epub
  uv run html2epub fetch <url> -o pages/      # save extracted article HTML for offline builds
  uv run html2epub inspect <input.html|dir|url>
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

### Building from the web

```bash
# Single URL -> single-article book (headings split it into chapters, as with a local file)
uv run html2epub build https://example.com/some-article -o out.epub

# Several URLs -> one chapter per URL, in the order listed (blank lines and # comments ignored)
uv run html2epub build --url-list urls.txt -o out.epub

# Tune the network step
uv run html2epub build <url> -o out.epub --timeout 30 --user-agent "my-reader/1.0"
```

A positional input and `--url-list` cannot be combined — supplying both is an error rather than a
silent drop.

### Determinism caveat for URLs

A direct URL -> EPUB build is only as reproducible as the page behind the URL: the site can change
its content, its markup, or serve you something different tomorrow. Building the same URL twice is
**not** guaranteed to produce the same bytes.

Use the two-step flow when reproducibility matters. `fetch` makes the network step explicit and
repeatable, writing the *extracted* article as `NNNN-<slug>.html` — numbered so the directory sorts
back into reading order:

```bash
uv run html2epub fetch --url-list urls.txt -o pages/
uv run html2epub build pages/ -o out.epub      # fully deterministic, and offline
```

Everything downstream of the fetch is byte-deterministic, so `pages/` is the artifact worth keeping
(and committing) if you need to rebuild the same book later.

### Extraction limits

- Article extraction is a heuristic. When it finds no main content, the build falls back to the
  whole `<body>` and prints a `[warning]` line — the book still builds, but that chapter will
  contain page furniture. Check the warning before trusting the output.
- URL safety is **scheme-only**: `http`/`https` are allowed, everything else is rejected, and the
  scheme is re-checked after redirects. There is no guard against URLs pointing at private or
  internal addresses — this is a local tool that fetches what you ask it to fetch.

## Design notes

- `models.py` is the hard internal boundary: parsing and chapter-splitting logic never see
  `ebooklib` types. One module per third-party library: only `epub_writer.py` imports `ebooklib`,
  only `fetch.py` imports `httpx`, only `extract.py` imports `trafilatura`.
- The URL path converges early: fetched pages become the same `RawDocument`s the file loader
  returns, so normalize -> structure -> write is shared with local input and untouched by it.
  One URL behaves like a single file; two or more behave like a directory.
- Metadata precedence: CLI flags > TOML sidecar > extracted (title/author/date) > scraped
  `<title>`/`<meta>` > fallback. For web sources the canonical URL is preferred as the EPUB
  identifier over the content hash, being stable and meaningful.
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
