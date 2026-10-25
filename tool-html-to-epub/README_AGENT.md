# README_AGENT

Notes for an AI agent or a maintainer who changes the code. A person who only runs the tool does
not need this file. Referenced from [README.md](README.md).

## Module map

`src/html_to_epub/` holds 12 modules. The pipeline order is load, normalize, structure, write.

| Module | Lines | Public names | Role |
| --- | --- | --- | --- |
| `__init__.py` | 1 | — | Package docstring only |
| `cli.py` | 255 | `main()` | argparse: `build`, `fetch`, `inspect`, `validate` |
| `config.py` | 28 | `BuildConfig` | Frozen settings for one run; validates `split_level` |
| `epub_writer.py` | 104 | `write_epub()` | Builds the book, then rewrites the zip |
| `extract.py` | 83 | `ExtractedArticle`, `extract_article()` | Article text out of a raw page |
| `fetch.py` | 59 | `FetchedPage`, `fetch_url()` | One HTTP(S) GET |
| `loaders.py` | 75 | `RawDocument`, `MetadataOverrides`, `load_documents()`, `load_metadata_sidecar()`, `scrape_title()`, `scrape_author()` | Disk input |
| `models.py` | 39 | `Metadata`, `Chapter`, `TocNode`, `BookModel` | The internal contract |
| `normalize.py` | 125 | `normalize_html()`, `render_node()` | Sanitize to XHTML |
| `pipeline.py` | 219 | `build_book_model()`, `build_book_model_from_html()`, `slugify_url()` | Orchestration |
| `structure.py` | 254 | `InputDoc`, `StructureResult`, `build_from_single_document()`, `build_from_directory()` | Chapters and TOC |
| `validator.py` | 153 | `Finding`, `validate_model()`, `validate_epub_file()` | Checks |

`tests/` holds 7 test modules and 54 tests. `tests/fixtures/` holds `single.html`,
`webpage.html`, `dated_article.html`, `meta.toml`, and `book/` with three numbered chapters.

## Design decisions

- **`models.py` is a hard boundary.** No third-party type crosses it. One module owns each
  third-party library: only `epub_writer.py` imports `ebooklib`, only `fetch.py` imports `httpx`,
  only `extract.py` imports `trafilatura`. Keep this rule when you add code. `beautifulsoup4` is
  the one exception: `loaders.py`, `extract.py`, `normalize.py`, and `structure.py` all import it.
- **The URL path converges early.** A fetched page becomes the same `RawDocument` that the file
  loader returns. Normalize, structure, and write are therefore shared with local input, and a
  change to the network step cannot reach them. One address behaves like one file. Two or more
  addresses behave like a directory.
- **Metadata precedence is data, not control flow.** `pipeline.py` takes the first source that has
  a value. Two of the rules are counter-intuitive, and both are deliberate: the author falls back
  to the title-cased domain, and the identifier prefers the canonical URL over the content hash.
  See [SCHEMA.md — Metadata precedence](SCHEMA.md#metadata-precedence).
- **`normalize.py` guarantees a parsable fragment.** The output always parses with
  `xml.etree.ElementTree`. Malformed XHTML is the most common reason an e-reader rejects a book,
  so this guarantee is the point of the module, not a side effect.
- **Determinism replaces the clock and the random source.** A BLAKE2b content hash replaces
  `uuid4()`, and a fixed constant replaces `datetime.now()`. The zip has fixed timestamps, a
  sorted entry order, and `mimetype` first and uncompressed. See
  [SCHEMA.md — Determinism](SCHEMA.md#determinism).

## Why a live URL build is not reproducible

The tool is deterministic downstream of the network. The network itself is not. The site can
change its content or its markup between two builds, so two builds of the same address can give
different bytes.

`fetch` makes the network step explicit and repeatable. It writes the *extracted* article, named
`NNNN-<slug>.html`, so the directory sorts back into reading order. `pages/` is the artifact worth
keeping if you must rebuild the same book later. See
[scripts-guide.md — Fetch, then build](scripts-guide.md#fetch-then-build) for the commands, and
[SCHEMA.md — Fetch output format](SCHEMA.md#fetch-output-format) for the naming rule.

## Extraction limits

- Article extraction is a heuristic. When `extract.py` finds no main content, the build falls back
  to the whole `<body>` and prints a `[warning]` line. The book still builds, but that chapter
  contains page furniture. Do not treat a successful exit code as proof of a clean extraction.
- URL safety is scheme-only. `cli.py` accepts `http` and `https`, rejects every other scheme, and
  re-checks the scheme after each redirect. There is no guard against an address that points at a
  private or internal host. This is a local tool that fetches what you tell it to fetch. Do not
  expose it to untrusted input without adding such a guard.

## Drift warnings

- **`uv run pytest` with no path fails.** pytest walks down from the project root and collects
  `extension/tests/`, which imports `html_to_epub_server`. That package is not installed in this
  project's `.venv`. The result is 3 collection errors. Always run `uv run pytest tests` here, and
  run the extension tests from `extension/` with its own environment.
- **`extension/` is a separate project root.** It has its own `pyproject.toml`, its own lockfile,
  and its own `.venv`. Do not add its dependencies to this `pyproject.toml`.
- **`extension/README.md` links to `README_AGENT.md` and `scripts-guide.md#safari-build` inside
  `extension/`. Neither file exists there.** Those two links are broken. Fix them in the extension
  project, not here.
- **The sibling `../tool-pdf-to-epub` repeats this contract; it does not import it.** Its
  `models.py`, `epub_writer.py`, and `validator.py` carry the same names — `Metadata`, `Chapter`,
  `TocNode`, `BookModel`, `Finding`, `validate_model()`, `validate_epub_file()` — and the same
  frozen-dataclass shape, but the code is a copy. Its `Chapter` adds `source_pages` and
  `confidence`, its `BookModel` adds `source_pages`, and it adds a `Warning` type that this
  project does not have. A fix in one project does not reach the other. See
  [../tool-pdf-to-epub/README.md](../tool-pdf-to-epub/README.md).
- **Second entry point.** `build_book_model_from_html()` in `pipeline.py` takes rendered HTML and a
  source address and skips the fetch step. The extension server is its only caller. A change to
  the fetch path must not change this function's behaviour.

## Scratch files at the project root

These files are session notes, not project artifacts. `.gitignore` already excludes all of them.
No document references them, and none should.

| File | What it is |
| --- | --- |
| `out.epub` | A leftover build output. `*.epub` is git-ignored |
| `handoff-tool-html-to-epub-extension.md` | Session handoff note |
| `plan-tool-html-to-epub-extension.md` | Session plan note |
| `claude_interaction_steps.md` | Session log |

## Docs map

| File | Audience | Content |
| --- | --- | --- |
| [README.md](README.md) | A person who wants to run the tool | What it is, the first run, the components, the layout |
| [scripts-guide.md](scripts-guide.md) | An operator | Every command, every flag, and the development tasks |
| [SCHEMA.md](SCHEMA.md) | A person who reads or writes the output | Pipeline, book model, element set, metadata rules, output formats, validator checks |
| [README_AGENT.md](README_AGENT.md) | An agent or a maintainer | Module map, design decisions, limits, drift warnings, scratch files |
| [extension/README.md](extension/README.md) | The extension user | The separate Chrome extension project |
