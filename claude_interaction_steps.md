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

## Branch `tool-html-to-epub` — new HTML → EPUB 3 CLI

- Plan written inline (architect-orchestrator skipped: greenfield tool, conventions read directly
  from the sibling `tool-sql-to-drawio`).
- `python-pro` — built `tool-html-to-epub/`: loaders/normalize/structure → `BookModel` (frozen
  dataclasses) → `epub_writer` (sole `ebooklib` importer) → validator, plus CLI
  `build`/`inspect`/`validate`, tests and fixtures.
- `test-automator` (independent) — found the tool was fundamentally broken despite green gates:
  every `chap_*.xhtml` in the output was 0 bytes (ebooklib silently swallows an lxml ValueError when
  content is a `str` carrying an encoding declaration). Also: duplicate + malformed
  `dcterms:modified`, genuinely non-deterministic output, validator passing empty books, CLI
  tracebacks on failure paths.
- `python-pro` (fresh, via handoff file) — fixed all four.
- `code-reviewer` — 4 findings; the real ones were cross-chapter anchor-id collisions rewriting
  links into the wrong chapter, and HTML comments leaking into the book as visible text.
- `python-pro` (fresh, via handoff file) — fixed all four, +2 regression tests.
- Orchestrator re-ran gates independently at each stage: 30 tests, ruff + mypy strict clean,
  byte-identical rebuilds, real chapter content, `validate` exit 0.
