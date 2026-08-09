# pdf-to-epub

Converts machine-readable PDFs into text-first, reflowable, deterministic EPUB 3 files. It is not a
visual-fidelity converter: it does not produce fixed-layout EPUB, does not guarantee good results on
magazines, brochures, or diagram-heavy PDFs, and does not preserve footnotes or sidebars as such.

## Resume

- **What it is**: a `pdf2epub` CLI that extracts text/structure from a PDF and writes a valid,
  byte-deterministic EPUB 3 file, with the same internal model/writer/validator contract as
  `tool-html-to-epub`.
- **Stack**: Python 3.11+, `uv`, PyMuPDF + pdfplumber for extraction, `ebooklib` for EPUB output,
  optional `ocrmypdf` for scanned PDFs.
- **How to run**:
  ```bash
  uv sync
  uv run pdf2epub build input.pdf -o output.epub
  ```

## Setup

```bash
uv sync
```

OCR support is optional and requires system binaries in addition to the Python extra:

```bash
uv sync --extra ocr
brew install tesseract ghostscript
```

## Usage

The CLI surface (implemented in a later stage) targets four subcommands:

- `pdf2epub build <input.pdf> -o <output.epub>` — run the full pipeline and write the EPUB.
- `pdf2epub inspect <input.pdf>` — print page/column/structure diagnostics without writing output.
- `pdf2epub classify <input.pdf>` — report whether the PDF is scanned or digital text.
- `pdf2epub validate <output.epub>` — re-run structural validation against an existing file.

## Design notes

- Images are always omitted from the generated EPUB in v1.
- Tables detected below the configured confidence threshold are omitted, with a `Warning` recorded
  on the `BookModel` and surfaced by the validator instead of silently dropped.
- `models.py` is a hard boundary: no third-party type crosses it, and each third-party library
  (`ebooklib`, `pymupdf`/`fitz`, `pdfplumber`) is imported from exactly one module.
- EPUB output is byte-for-byte deterministic: fixed zip timestamps, sorted entry order, `mimetype`
  stored first and uncompressed.

## Tests

```bash
uv run pytest
```
