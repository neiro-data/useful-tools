# tool-html-to-epub — v2: build an EPUB directly from a web link

## Context

v1 (PR #42, open, unmerged) converts a local HTML file or directory into a deterministic EPUB 3.
It cannot take a URL: `loaders.load_documents` (`loaders.py:31`) accepts only a `Path` with an
`.html`/`.xhtml` suffix or a directory, so `html2epub build https://…` fails with
`unsupported input file type`. There is no HTTP client in the project.

Fetching alone would not be enough. `normalize.py` removes *tags* but preserves all *text*, so a real
web page would yield a chapter padded with nav menus, cookie banners, "related articles" and footers.
Useful URL support therefore needs two new capabilities: **fetch** and **main-content extraction**.

Outcome: `html2epub build <url> -o out.epub` produces a clean, readable single-article book;
`--url-list urls.txt` produces a multi-chapter book; `html2epub fetch` preserves the byte-determinism
guarantee by making the network step explicit and repeatable offline.

## Status of v1 — no outstanding work

Plan fully executed: modules, 30 tests, tool `README.md` (`## Resume`), tool
`claude_interaction_steps.md`, root `README.md` entry, commit `f696d5d`, PR #42 into `main` with
`neiro` as reviewer. The only remaining v1 action is human: review and merge #42. Nothing is being
added here as filler.

## Decisions (confirmed with the user)

| Question | Decision |
|---|---|
| Content extraction | `trafilatura` — boilerplate removal plus title/author/date metadata |
| URL scope | Single URL **and** `--url-list <file>` (one URL per line); no crawling |
| Determinism | New `fetch` subcommand saves extracted HTML to disk; direct URL→EPUB kept as a convenience with a documented caveat |

## Branching

PR #42 is not merged. Cut `feat/html-to-epub-url-input` **from `tool-html-to-epub`**, not from `main`,
so this stacks on the unmerged work. Target the PR at `tool-html-to-epub`, or at `main` once #42 lands.

## Design

Two new modules, each a single-library isolation boundary, mirroring how `epub_writer.py` is the only
module that imports `ebooklib`:

- **`src/html_to_epub/fetch.py`** — the only module importing `httpx`. `fetch_url(url, *, timeout,
  user_agent) -> FetchedPage(url, final_url, html)`. Scheme allowlist `http`/`https` only; explicit
  timeout (ruff `S` will flag a missing one); cap redirects and response size; raise `ValueError`
  with a one-line message on non-2xx, bad scheme, or oversize body so the existing
  `cli._build_model_or_none` handler reports it as `[error] …` with exit 1.
- **`src/html_to_epub/extract.py`** — the only module importing `trafilatura`.
  `extract_article(html, base_url) -> ExtractedArticle(html_fragment, title|None, author|None,
  date|None, canonical_url|None)`. Falls back to the whole `<body>` when extraction returns nothing,
  emitting a warning rather than failing. Absolutizes relative `href`s against `base_url` so links in
  the book still resolve.

Wiring, all small and additive:

- **`config.py`** — extend `BuildConfig` with `urls: tuple[str, ...] = ()`, `timeout: float = 20.0`,
  `user_agent: str | None = None`. `input_path` becomes optional so a URL-only build is representable.
- **`pipeline.py:25` `build_book_model`** — before the existing `load_documents` path, branch on
  whether the config carries URLs. URLs produce the same `list[RawDocument]` the loader returns, so
  everything downstream (`normalize` → `structure` → `BookModel` → `epub_writer`) is untouched. One URL
  → single-document mode (headings split it, as today). Two or more → directory mode, one chapter per
  URL, order = the order given.
- **Metadata precedence** stays as documented, with the extractor slotted in below the sidecar:
  CLI flags > TOML sidecar > extracted (`title`/`author`/`date`) > scraped `<title>` > fallback.
  `identifier` defaults to the canonical URL when present — a stable, meaningful ID, better than the
  BLAKE2b content hash for web sources. `modified` uses the article's published date if it parses as
  `CCYY-MM-DDThh:mm:ssZ`, otherwise the existing `1970-01-01T00:00:00Z` constant.
- **`cli.py`** — `build`/`inspect` positional `input` also accepts an `http(s)://` URL; add
  `--url-list <file>`, `--timeout`, `--user-agent`. New `fetch` subcommand:
  `html2epub fetch <url|--url-list f> -o <dir>` writes one numbered `NNNN-<slug>.html` per URL
  (extracted content, deterministic filenames so the directory sorts into reading order), then
  `build <dir>` is fully deterministic and offline. Reuse `_build_model_or_none` for error handling.
- **`pyproject.toml`** — `uv add httpx trafilatura`. Do not hand-edit.

## Tests (`tests/test_fetch.py`, `tests/test_extract.py`, additions to `test_cli.py`)

No network, per the repo default of mocking external systems. Monkeypatch `fetch.fetch_url` so the CLI
and pipeline tests run against a fixture. Add `tests/fixtures/webpage.html` — a realistic messy page
(nav, aside, cookie banner, footer, one real `<article>`).

- extraction keeps the article text and drops nav/aside/footer/cookie-banner text;
- relative `href`/anchor absolutization against the base URL;
- fallback path when trafilatura extracts nothing;
- scheme rejection (`file://`, `ftp://`) and non-2xx → `ValueError`, surfaced as `[error]` + exit 1;
- multi-URL build yields chapters in the given order, one per URL;
- `fetch` writes deterministic filenames, and `build` over that directory is byte-identical across
  two runs;
- metadata precedence: CLI flag beats sidecar beats extracted date/title.

## Execution — ORCHESTRATION.md pipeline

`Pipeline: plan skipped — architect-orchestrator not spawned; scope is bounded to files read in full
inline (loaders, pipeline, config, cli).`

0. Copy this plan to `tool-html-to-epub/PLAN-url-input.md` on the branch, so it is traceable in-repo.
1. **`python-pro`** implements against this plan. Brief carries the two module contracts, the
   isolation rule, the no-network test constraint, and verbatim: `Report back in ≤15 lines: files
   touched, decisions, risks, open questions. No transcript, no narration.`
2. **`test-automator`**, spawned independently from branch + diff + acceptance criteria only, runs the
   gates itself. It must verify against a *real* extracted archive — v1's lesson was that green gates
   are not evidence the tool works.
3. **`code-reviewer`**; any defects go to a **fresh** `python-pro` through a scratchpad
   `handoff-feat-html-to-epub-url-input.md`, never by resuming the implementer.
4. Orchestrator re-runs the gates, updates the tool `README.md` (`## Resume` + URL usage + the
   determinism caveat), appends to `tool-html-to-epub/claude_interaction_steps.md`, commits
   `feat(html-to-epub): …` with an `Agent:` trailer, pushes, opens a PR with the user as reviewer.
   **Never merges.**
5. Report per-stage token lines and the closing cache table via `scripts/cache_report.sh`.

## To-Dos

- [ ] T0 — branch `feat/html-to-epub-url-input` from `tool-html-to-epub`; copy this plan to
      `tool-html-to-epub/PLAN-url-input.md`
- [ ] T1 — `uv add httpx trafilatura`
- [ ] T2 — `fetch.py`: `fetch_url` + `FetchedPage`, scheme allowlist, timeout, size/redirect caps,
      `ValueError` on failure
- [ ] T3 — `extract.py`: `extract_article` + `ExtractedArticle`, whole-`<body>` fallback, relative-href
      absolutization
- [ ] T4 — `config.py`: `urls`, `timeout`, `user_agent`; `input_path` optional
- [ ] T5 — `pipeline.py`: URL branch producing `RawDocument`s; 1 URL → single-doc mode, N → directory
      mode; extracted metadata slotted below the sidecar; canonical URL as default identifier
- [ ] T6 — `cli.py`: URL positional, `--url-list`, `--timeout`, `--user-agent`, new `fetch` subcommand
- [ ] T7 — tests: `test_fetch.py`, `test_extract.py`, `test_cli.py` additions, `fixtures/webpage.html`;
      no network
- [ ] T8 — gates green: `ruff check`, `ruff format --check`, `mypy` strict, `pytest`
- [ ] T9 — manual verification block below, run by the orchestrator, not just claimed by an agent
- [ ] T10 — README (`## Resume`, URL usage, determinism caveat) + `claude_interaction_steps.md` entry
- [ ] T11 — commit, push, open PR with `neiro` as reviewer; do not merge
- [ ] T12 — token lines + cache table

## Verification

```bash
cd tool-html-to-epub
uv sync
uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest

# offline gates above must be clean; the two below need network
uv run html2epub build https://example.com/some-article -o /tmp/web.epub
uv run html2epub validate /tmp/web.epub                       # exit 0
unzip -p /tmp/web.epub EPUB/chap_0001.xhtml | head -c 400     # real article text, no nav/footer

# deterministic two-step
uv run html2epub fetch https://example.com/some-article -o /tmp/pages/
uv run html2epub build /tmp/pages/ -o /tmp/a.epub
sleep 2 && uv run html2epub build /tmp/pages/ -o /tmp/b.epub
cmp /tmp/a.epub /tmp/b.epub                                    # byte-identical

uv run html2epub build ftp://example.com/x -o /tmp/x.epub      # [error] … , exit 1
```

Acceptance: a URL produces a readable EPUB whose chapter is the article and not the page furniture;
a URL list produces one chapter per URL in order; `fetch` + `build` is byte-deterministic and works
offline; bad schemes and HTTP failures exit 1 with a single `[error]` line, never a traceback; v1's
local-file and directory paths behave exactly as before.
