# Claude interaction log — webpage-time-tracker-app

Append-only. Terse entries: branch purpose + what was done.

---

## 2026-07-28 — `feat/webpage-time-tracker-userscript` (from `webpage-time-tracker`)

Greenfield. Scoped the idea (timer + nudge when over a threshold on time-sink pages) from scratch:
feasibility discussion first, no code until the design was settled.

- Ruled out Safari as first target — Safari Web Extensions need an Xcode app wrapper, signing resets
  on every restart without a paid Apple dev account, and `chrome.idle` is unsupported. Chrome first.
- Chose a Tampermonkey userscript over an MV3 extension for v0.1: no store, no signing, no build,
  and it validates the real question (do the nudges change behaviour?) cheaply.
- Decisions: single pooled budget across sites (not per-site), 45 min/day, daily reset at 04:00,
  rules = YouTube Shorts + Instagram Reels + X. Memes dropped.
- Built `webpage-time-tracker.user.js` (441 lines, no deps) + README.
- Notable: `GM_setValue` rather than `localStorage` for state, since `localStorage` is per-origin and
  can't pool a budget across origins. Shadow DOM for the overlay. `@match *://*/*` + host early-out
  so the rules list lives in one place.
- No specialist agents used — session config disallows spawning them unprompted; declared this
  rather than skipping the pipeline silently.
- Verified: `node --check` passes, no imports. Runtime behaviour needs manual testing in Chrome
  (can't drive Tampermonkey from here).

## 2026-07-28 — `feat/per-site-budgets-and-always-on-badge` (from `webpage-time-tracker`)

v0.2 PR 1 of 2. Pooled budget → per-site limits.

- State `wtt.state.v1` {day, seconds} → `wtt.state.v2` { days: { day: { site: seconds } } }, 14-day
  rolling history, pruned on read (ISO keys sort as dates). No migration — v1 held only today.
- `resync()` now merges per site, so two tabs on different tracked sites do not clobber each other.
- Each rule carries `limitMinutes` (Shorts 15, Reels 15, X 30); `budgetMinutes` deleted. Escalation
  ladder + snooze are per site.
- Badge always visible on a tracked page, dimmed under 50%; dropped the `at: 0.5` LEVELS entry since
  the badge no longer gates on a level.
- Menu: per-site status + 7-day trend; reset/grant act on the active site only.
- No specialist agents — session config disallows spawning them unprompted; declared, not skipped.
- Verified: `node --check` passes. Runtime needs manual Chrome testing.
