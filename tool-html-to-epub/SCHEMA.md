# SCHEMA

The internal data contract, the metadata rules, and the two output formats.
Referenced from [README.md](README.md).

This project uses no database. The persistent formats are the `.epub` file and the `fetch` output
directory.

## Pipeline

The pipeline has one shape for every input form.

```
file / directory ──┐
                   ├─> RawDocument ─> normalize ─> structure ─> BookModel ─> EPUB 3 file
URL / --url-list ──┘        (fetch + extract first)
```

`pipeline.py` runs the steps. A fetched page becomes the same `RawDocument` that the file loader
returns. One URL behaves like one file. Two or more URLs behave like a directory.

`build_book_model_from_html()` is a second entry point. It takes rendered HTML and a source URL,
and it skips the fetch step. The browser extension server calls it.

## The book model

`models.py` holds the contract. No third-party type crosses this module.

| Type | Fields |
| --- | --- |
| `Metadata` | `identifier`, `title`, `language`, `author`, `publisher`, `modified` |
| `Chapter` | `id`, `title`, `file_name`, `body_xhtml`, `anchors` |
| `TocNode` | `title`, `href`, `children` |
| `BookModel` | `metadata`, `chapters`, `toc`, `spine` |

Every type is a frozen dataclass. Every collection field is a tuple.

`spine` holds chapter file names in reading order.

### Chapter identity

`structure.py` assigns the id and the filename in document order:

- id: `chap_0001`, `chap_0002`, …
- filename: `chap_0001.xhtml`, `chap_0002.xhtml`, …

The numbers depend only on the input order, so a rebuild produces the same names.

`anchors` holds the `id` attributes that the chapter owns. `structure.py` uses this map to rewrite
a same-document link `href="#x"` to the chapter file that owns `#x`. A link to an unknown anchor
becomes an unresolved href, and the CLI reports it as a warning.

## Sanitized element set

`normalize.py` returns a well-formed XHTML body fragment. The output always parses with
`xml.etree.ElementTree`. Malformed XHTML is the most common reason an e-reader rejects a book.

| Class | Elements |
| --- | --- |
| Dropped with their content | `script`, `style`, `img`, `picture`, `video`, `iframe` |
| Kept | `h1`–`h6`, `p`, `ul`, `ol`, `li`, `blockquote`, `pre`, `code`, `a`, `em`, `strong`, `hr`, `table`, `thead`, `tbody`, `tr`, `td`, `th`, `body`, `br` |
| Self-closed | `hr`, `br` |

`normalize.py` unwraps every other element. The text survives, the tag does not. No `style`
attribute and no `on*` attribute survives.

## Metadata precedence

`pipeline.py` resolves each field from the first source that has a value.

| Field | Order, highest first |
| --- | --- |
| `title` | CLI flag, TOML sidecar, extracted title, scraped `<title>`, input filename stem |
| `author` | CLI flag, TOML sidecar, extracted author, scraped `<meta>`, domain name |
| `language` | CLI flag, TOML sidecar, `en` |
| `identifier` | CLI flag, TOML sidecar, canonical URL, content hash |
| `modified` | TOML sidecar `date`, extracted date, `1970-01-01T00:00:00Z` |

Two of these rules are counter-intuitive.

### The author falls back to the domain

A URL source often has no byline. The tool then title-cases the domain and uses it as the author.
`tigerdata.com` becomes `Tigerdata`. The book is never unattributed.

### The identifier prefers the URL

For a web source the canonical URL wins over the content hash. A URL is stable and meaningful. The
content hash is a BLAKE2b digest of the normalized fragments, with a 16-byte digest size.

## TOML metadata sidecar

`--metadata <file>` reads these keys. Every key is optional.

| Key | Type | Example |
| --- | --- | --- |
| `title` | string | `"My Test Book"` |
| `author` | string | `"Test Author"` |
| `language` | string | `"en"` |
| `identifier` | string | `"urn:uuid:test-book-001"` |
| `date` | string | `"2024-01-01T00:00:00Z"` |

`date` sets the EPUB `dcterms:modified` value. EPUB 3 requires the form `CCYY-MM-DDThh:mm:ssZ`.

`tests/fixtures/meta.toml` is a working example.

## EPUB output layout

`epub_writer.py` builds the book with `ebooklib`, then rewrites the zip for byte-determinism.

| Entry | Rule |
| --- | --- |
| `mimetype` | First entry, stored uncompressed |
| every other entry | Sorted by name, deflated |
| every entry | Fixed timestamp `2000-01-01 00:00:00`, mode `0o644` |

The book carries an EPUB 3 nav document and an NCX item. `nav` is the first spine entry. The
chapter files follow in `spine` order.

## Fetch output format

`fetch` writes one file per URL into the output directory:

```
0000-<slug>.html
0001-<slug>.html
```

The index is the position in the URL list, zero-based and four digits wide. The slug comes from the
final URL, after redirects. Each file holds the extracted article fragment, not the raw page.

The four-digit prefix makes a filename sort equal to the reading order, so `build <dir>` rebuilds
the same book.

## Determinism

The same input and the same configuration always produce the same output bytes. Three rules make
this true.

1. No `uuid4()` and no `datetime.now()` reaches the output. The identifier falls back to a content
   hash. The `modified` field falls back to a fixed constant.
2. The zip has fixed timestamps, a sorted entry order, and `mimetype` first and uncompressed.
3. Chapter ids and filenames come from the document order alone.

A build from a live URL is the one exception. The page behind the URL can change. See
[scripts-guide.md — Fetch, then build](scripts-guide.md#fetch-then-build).

## What the validator checks

`validate_model()` runs on the model before the write. `validate_epub_file()` runs on a written
file. Both return a list of findings, each `error` or `warning`.

| Check | Where |
| --- | --- |
| `identifier`, `title`, `language` are not empty | model |
| `spine` references a known chapter | model |
| no chapter has an empty body | model |
| every TOC href resolves to a known file and anchor | model |
| `mimetype` is the first entry and is stored | file |
| `META-INF/container.xml` and its rootfile exist | file |
| `content.opf` is well-formed and has `<metadata>` | file |
| a manifest item has `properties="nav"` | file |
| every spine `idref` is in the manifest | file |
| every spine item exists, is not empty, and parses as XML | file |

## Last verified

Verified on 2026-09-02 against the working tree: 12 modules in `src/html_to_epub/`, 7 test modules
in `tests/`, and 54 tests that pass with `uv run pytest tests`.

For the per-module map and the design decisions behind this contract, see
[README_AGENT.md — Module map](README_AGENT.md#module-map).
