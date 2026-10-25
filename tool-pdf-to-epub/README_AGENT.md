# README_AGENT — pdf-to-epub

Notes for an AI agent or a maintainer who changes the code. A person who only converts a PDF does
not need this file. Referenced from [README.md](README.md).

## Shared contract with tool-html-to-epub

`pdf-to-epub` and its sibling [`../tool-html-to-epub`](../tool-html-to-epub/README.md) share one
model/writer/validator contract. The two projects are separate `uv` projects. They share no code.
They share the shape of the three modules below, so a change to one is a candidate change to the
other.

| Module | Contract |
| --- | --- |
| `models.py` | The frozen dataclasses `Metadata`, `Chapter`, `TocNode`, and `BookModel`. No third-party type crosses this module. |
| `epub_writer.py` | `write_epub(book_model: BookModel, output_path: Path) -> None`. The only importer of `ebooklib`. |
| `validator.py` | `Finding(level, message)`, `validate_model(book) -> list[Finding]`, and `validate_epub_file(path) -> list[Finding]`. |

The four common dataclass fields are identical in both projects:

- `Metadata(identifier, title, language, author, publisher, modified)`
- `Chapter(id, title, file_name, body_xhtml, anchors)`
- `TocNode(title, href, children)`
- `BookModel(metadata, chapters, toc, spine)`

`pdf-to-epub` extends the shape. It adds a `Warning(code, message, page, severity)` dataclass, the
fields `Chapter.source_pages` and `Chapter.confidence`, and the fields `BookModel.source_pages`,
`BookModel.confidence`, and `BookModel.warnings`. Every added field has a default value, so the
sibling shape stays valid. `tool-html-to-epub` has no `Warning` class and no confidence fields.

Both writers produce the same deterministic zip: fixed entry timestamps, sorted entry order, and
`mimetype` stored first and uncompressed.

## Design notes

- The EPUB omits images in v1. `pipeline.py` counts the pages that carry an image and records one
  `images.omitted` warning. The validator prints that warning.
- `structure.py` tags a short paragraph next to a figure or a table as a caption. `xhtml.py` styles
  it with `p.caption` from the shipped stylesheet, so a caption does not read as a body paragraph.
- `tables.py` returns `None` for a table below the confidence threshold. `pipeline.py` counts the
  rejection and lowers the page score. The table is omitted, not dropped in silence.
- `models.py` is a hard boundary. Each third-party library has exactly one import site: `ebooklib`
  in `epub_writer.py`, `fitz` (PyMuPDF) in `pdf_source.py`, `pdfplumber` in `plumber_source.py`,
  and `subprocess` in `ocr.py`.
- `pipeline.py` derives the EPUB identifier from a BLAKE2b hash of the extracted blocks when the
  metadata sidecar gives no identifier. `epub_writer.py` uses a fixed modification date. The two
  rules together make the output byte-deterministic.
- `build` fails when the document confidence is below `--min-confidence`, when the validator
  reports an error, or when the extraction produces zero characters.

## Module map

| Module | Purpose | Third-party import |
| --- | --- | --- |
| `cli.py` | The `pdf2epub` argparse entry point and the four subcommands. | none |
| `config.py` | `BuildConfig` and the `Thresholds` dataclass of tunable numbers. | none |
| `models.py` | The internal data contract. | none |
| `pdf_source.py` | Page, word, outline, and metadata extraction. | `fitz` (PyMuPDF) |
| `plumber_source.py` | Raw table extraction. | `pdfplumber` |
| `ocr.py` | Runs `ocrmypdf` on a scanned or mixed PDF. | `subprocess` |
| `classify.py` | Per-page and per-document kind: scanned, digital, or mixed. | none |
| `layout.py` | Column and gutter detection, then zone segmentation. | none |
| `reconstruct.py` | Reading-order blocks and paragraph joins from zones. | none |
| `structure.py` | Heading inference, caption tagging, chapters, and the TOC. | none |
| `tables.py` | Renders a high-confidence table to XHTML. | none |
| `confidence.py` | Page, section, and document confidence scores. | none |
| `xhtml.py` | XHTML helpers and the base stylesheet. | none |
| `validator.py` | `BookModel` checks before write, zip checks after write. | none |
| `epub_writer.py` | Deterministic EPUB 3 output. | `ebooklib` |
| `pipeline.py` | The only module that knows the end-to-end flow. | none |

`pipeline._analyze` runs the stages in this order: load, classify, optional OCR, columns, zones,
blocks, running-head strip, tables, structure, confidence, metadata, `BookModel`.

## Thresholds

`config.Thresholds` holds every tunable number in one frozen dataclass. Read
`src/pdf_to_epub/config.py` before you add a constant to another module. Each field carries a
trailing comment that states its meaning. `BuildConfig.thresholds` holds the instance, so a test
can override one number without a monkeypatch.

## Checks before you commit

```bash
uv run pytest        # 75 tests
uv run ruff check .  # select = E, F, I, W, UP, S, B; line length 100
uv run mypy          # strict, over src and tests
```

`mypy` ignores missing imports for `ebooklib`, `fitz`, and `pdfplumber` only. Do not widen that
list. `ruff` allows `assert` in `tests/` only.

## Docs map

| File | Content |
| --- | --- |
| [README.md](README.md) | The summary, the quick start, the CLI commands, and the layout. |
| [README_AGENT.md](README_AGENT.md) | The shared contract, the design notes, the module map, and the checks. |
| [`../tool-html-to-epub/README.md`](../tool-html-to-epub/README.md) | The sibling project that shares the model, writer, and validator contract. |
