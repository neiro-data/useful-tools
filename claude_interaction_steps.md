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
