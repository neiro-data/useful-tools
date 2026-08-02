# Claude interaction steps

## 2026-07-28 — `feat/site-dialog-regex-suggest` (branched from `webpage-time-tracker`)

Suggest button in the Add/Edit site dialog to fill Path regex (and Host regex in Advanced mode)
from a domain, local table first, `claude-haiku-4-5` fallback.

- Plan-mode Q&A: chose local table + explicit Claude button, manual trigger, scoped to the
  regex fields only.
- Step 0 verification changed the design: `models.host_regex()` already derives the host
  pattern from a plain domain, so the planned curated host table was dropped as redundant.
  Target narrowed to Path regex.
- `python-pro` — new `config_gui/regex_suggest.py` (KNOWN_PATHS table, Claude fallback, disk
  cache, validation, preview samples), `SuggestPreviewDialog` + threaded call in `app.py`,
  `models.normalize_domain()` extracted, `store.write_atomic()` extracted,
  `tests/test_regex_suggest.py`.
- `code-reviewer` — 8 findings. Two serious and reproduced: `validate()` accepted
  `youtube.com$` and `.*$` as host regexes (matched `evilyoutube.com` / everything); and every
  correct path suggestion showed a false red row in the preview, defeating the check meant to
  catch the first. Plus cache-before-validate poisoning, non-atomic cache write, JS-incompatible
  constructs, daemon-thread TclError.
- `python-pro` (resumed) — all 8 fixed; re-verified independently. ruff + mypy strict clean,
  124 tests pass. Not committed.

## tool-pdf-to-epub — PDF → EPUB 3 converter (branch `tool-pdf-to-epub`)

New sibling to `tool-html-to-epub`: CLI `pdf2epub` converting machine-readable PDFs into
text-first, reflowable, deterministic EPUB 3. Multi-column layout is a first-class case; images
always omitted in v1; low-confidence tables omitted with a warning.

Worked in an isolated git worktree (`.claude/worktrees/pdf-to-epub`) rather than checking out the
branch — another agent was concurrently editing `tool-html-to-epub/` in the shared tree.

- `python-pro` #1 — scaffold: pyproject/uv, `models.py` (+`Warning`, `source_pages`, `confidence`),
  `config.py` (`Thresholds` holds every tunable), `xhtml.py`; `epub_writer.py` + `validator.py`
  ported from the sibling with the deterministic zip rewrite intact.
- `python-pro` #2 — recovery core: `pdf_source` (sole `fitz` importer), `classify`, `layout`
  (x-projection gutter detection validated by strip persistence), `reconstruct` (band/column-major
  reading order, running-head stripping, hyphen + cross-page paragraph joining), `plumber_source`,
  `tables`, `ocr` (shells `ocrmypdf`, optional extra).
- `python-pro` #3 — assembly: `structure` (heading inference, chapter split, PDF-outline-preferred
  TOC), `confidence`, `pipeline`, `cli`; plus two carry-over fixes (`Block.pages` tuple,
  `ColumnResult` warning channel).
- `test-automator` — independent gate: PASS. Added cross-process determinism, `--metadata`,
  `--no-tables` coverage.
- `code-reviewer` — 3 confirmed defects: non-deterministic font-key tie-break via `set` iteration
  (broke the byte-identical guarantee), `fitz.FileDataError` escaping the CLI error contract
  (traceback on corrupt PDF), and pdfplumber re-parsing the whole document once per page.
- `python-pro` (fresh, via handoff file) — all 3 fixed. Verified independently: identical output
  across `PYTHONHASHSEED=1`/`2`, clean `[error]` on a corrupt PDF, single `pdfplumber.open`.

Gates at commit: ruff clean, mypy strict clean, 70 tests pass. Deferred by design: table blocks
appended at end of page rather than in reading order; chapter-opener heuristic lacks a y-check.
