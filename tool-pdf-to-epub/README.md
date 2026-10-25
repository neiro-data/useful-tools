# pdf-to-epub

Converts a machine-readable PDF into a text-first, reflowable, deterministic EPUB 3 file.

## Resume

- **What it is**: a `pdf2epub` command-line interface (CLI). It extracts the text and the structure
  from a PDF file. It then writes a valid, byte-deterministic EPUB 3 file. The same input and the
  same configuration always produce the same output bytes.
- **Stack**: Python 3.11+, `uv`, `src/` layout. Runtime dependencies: `pymupdf` and `pdfplumber`
  for extraction, `ebooklib` for the EPUB output, and `lxml`. Development: `pytest`, `ruff`, and
  `mypy` in strict mode. Optional extra: `ocrmypdf` for scanned PDFs.
- **Entry point**: `pdf2epub`, declared in `pyproject.toml` and implemented in
  `src/pdf_to_epub/cli.py`.
- **Host requirements**: `uv` and Python 3.11 or later. OCR also needs the `tesseract` and
  `ghostscript` binaries.
- **Limits**: this is not a visual-fidelity converter. It does not write fixed-layout EPUB. It
  omits all images. It does not keep footnotes or sidebars as such. Magazines, brochures, and
  diagram-heavy PDFs give poor results.

## Agent read

If you are an AI agent, read also [README_AGENT.md](README_AGENT.md).

## Quick start

```bash
uv sync                                          # install the runtime and dev dependencies
uv run pdf2epub classify input.pdf               # is the PDF scanned or digital text?
uv run pdf2epub inspect input.pdf                # pages, chapters, and confidence, no output file
uv run pdf2epub build input.pdf -o output.epub   # write the EPUB
uv run pdf2epub validate output.epub             # re-check a written file
```

`build` prints a diagnostic report to stderr, then `wrote output.epub` to stdout. It exits with
code 1 when the validator reports an error, when the document confidence is below
`--min-confidence`, or when the extraction produces zero characters.

For a scanned PDF, install the OCR extra first, then pass `--ocr`:

```bash
uv sync --extra ocr
brew install tesseract ghostscript
uv run pdf2epub build scan.pdf -o output.epub --ocr
```

## CLI commands

The CLI has four subcommands. `build` and `inspect` run the same pipeline; only `build` writes a
file. Use `inspect` to check the derived chapters before you commit to an output file.

| Command | Result |
| --- | --- |
| `pdf2epub build <input.pdf> -o <output.epub>` | Runs the full pipeline and writes the EPUB. |
| `pdf2epub inspect <input.pdf>` | Prints the pages, the chapters, and the confidence scores. |
| `pdf2epub classify <input.pdf>` | Reports the kind and the column count, per page and per document. |
| `pdf2epub validate <output.epub>` | Re-runs the structural checks against a written file. |

`build` and `inspect` accept the same options:

| Option | Default | Result |
| --- | --- | --- |
| `--ocr` | off | Runs `ocrmypdf` first when the document is scanned or mixed. |
| `--split-level {1,2,3}` | `1` | Sets the heading level that starts a new chapter. |
| `--min-confidence <float>` | `0.35` | Fails the build below this document confidence. |
| `--metadata <file.toml>` | none | Reads a TOML sidecar that overrides the PDF metadata. |
| `--no-tables` | off | Skips table extraction. |

The metadata sidecar accepts the keys `title`, `author`, `publisher`, `language`, and
`identifier`. A sidecar key wins over the value in the PDF.

## Output

The EPUB carries one XHTML file per chapter, a navigation document, an NCX file, and one
stylesheet at `style/stylesheet.css`. The stylesheet styles the headings, the tables, and the
figure captions (`p.caption`). The writer omits every image.

The zip is byte-deterministic: fixed entry timestamps, sorted entry order, and `mimetype` stored
first and uncompressed. See
[README_AGENT.md — Design notes](README_AGENT.md#design-notes) for the rules that produce it.

## Tests

```bash
uv run pytest        # 75 tests
uv run ruff check .
uv run mypy
```

## Layout

```
README.md                      this file: summary, quick start, CLI commands
README_AGENT.md                shared contract, design notes, module map, checks
pyproject.toml                 project metadata, dependencies, ruff and mypy configuration
src/pdf_to_epub/
  cli.py                       the pdf2epub entry point
  config.py                    BuildConfig and Thresholds
  models.py                    the internal data contract
  pdf_source.py                page and outline extraction (PyMuPDF)
  plumber_source.py            raw table extraction (pdfplumber)
  ocr.py                       ocrmypdf invocation
  classify.py                  scanned, digital, or mixed
  layout.py                    column and zone detection
  reconstruct.py               reading-order blocks and paragraphs
  structure.py                 headings, captions, chapters, and the TOC
  tables.py                    table to XHTML
  confidence.py                page, section, and document scores
  xhtml.py                     XHTML helpers and the base stylesheet
  validator.py                 checks before and after the write
  epub_writer.py               deterministic EPUB 3 output (ebooklib)
  pipeline.py                  the end-to-end flow
tests/                         11 test modules
  fixtures/make_pdfs.py        builds the synthetic PDFs the tests use
```

The sibling project [`../tool-html-to-epub`](../tool-html-to-epub/README.md) shares the model,
writer, and validator contract. Change both together.
