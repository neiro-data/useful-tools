# Time Tracker — Frontend

React SPA for the personal, offline-first time tracker. Implements the **Today**, **Week**, and
**Month** screens against the FastAPI backend in `../app` and the design system in `../design`.

- **Stack:** Vite + React 19 + TypeScript (strict), `react-router-dom` for routing.
- **Design:** imports `../design/tokens.css` globally (see `src/main.tsx`) — no ad hoc colors;
  everything renders via `var(--...)` tokens. Light/dark follows `prefers-color-scheme`
  automatically (no manual toggle in this phase, per `design/DESIGN_SYSTEM.md` §5.4).
- **API contract:** `src/api/` is a typed client for `app/API_CONTRACT.md` /
  `app/schemas.py` — one module per resource (`categories`, `tags`, `entries`, `timer`, `today`),
  built on a shared `apiRequest()` fetch wrapper (`src/api/client.ts`).

## Running locally

This app has two halves that both need to be running:

1. **Backend** (from the repo root, `time-tracker-app/`):

   ```bash
   uv sync
   uv run uvicorn app.main:app --reload
   ```

   Serves the API at `http://127.0.0.1:8000` (see `app/API_CONTRACT.md`).

2. **Frontend** (from this directory, `time-tracker-app/frontend/`):

   ```bash
   npm install
   npm run dev
   ```

   Serves the SPA at `http://localhost:5173` (Vite's default). The dev server proxies any
   `/api/*` request to the backend origin (see "Proxy / origin config" below) — the app itself
   only ever calls relative `/api/...` paths, so there's no CORS configuration to keep in sync.

## Proxy / origin config

`vite.config.ts` configures a dev-only proxy:

```ts
server: {
  proxy: {
    "/api": {
      target: process.env.VITE_BACKEND_ORIGIN ?? "http://127.0.0.1:8000",
      changeOrigin: true,
      rewrite: (p) => p.replace(/^\/api/, ""),
    },
  },
},
```

- The app calls `/api/today`, `/api/entries`, etc. — Vite strips the `/api` prefix and forwards
  the request to the backend's actual root-mounted routes (`/today`, `/entries`, ... per
  `app/API_CONTRACT.md`).
- Override the backend origin (e.g. a non-default port) with the `VITE_BACKEND_ORIGIN` env var
  before running `npm run dev`.
- A production build (`npm run build`) has no dev proxy — if you ever serve the built `dist/`
  bundle separately from the backend, put a reverse proxy (nginx, Caddy, etc.) in front with the
  same `/api` → backend-origin rewrite, or adjust `src/api/client.ts`'s `API_PREFIX`.

## Error handling

Every API call goes through `apiRequest()` (`src/api/client.ts`), which normalizes **all**
non-2xx responses into a single `ApiError` (`src/api/errors.ts`) carrying the backend's stable
`code` / human-readable `message` / structured `details` (per the error envelope in
`app/API_CONTRACT.md`). Call sites branch on `error.code` rather than parsing messages or status
codes, e.g.:

```ts
try {
  await startTimer({ title });
} catch (err) {
  if (err instanceof ApiError && err.isTimerAlreadyRunning) {
    // err.runningEntryId is the id of the entry already in progress
  }
}
```

The Today screen's `TodayPage` shows a concrete example: starting a timer while one is already
running surfaces the `409 timer_already_running` conflict as an inline banner ("Stop it and start
this instead" / "Cancel") rather than a thrown/unhandled exception — see
`src/pages/Today/TodayPage.tsx`.

## Project layout

```
frontend/
├── src/
│   ├── api/            typed API client (client.ts, errors.ts, types.ts, one module per resource)
│   ├── components/     shared UI: EntryRow, CategoryChip, TagChip, TimerWidget, SegmentedBreakdown,
│   │                    DayGroup, ManualEntryForm, CategoryPicker, TimerBanner, AppShell, Skeleton...
│   ├── hooks/           useLiveTimer, useRunningTimer, usePeriodEntries
│   ├── pages/           Today, Week, Month (routed via react-router-dom)
│   ├── utils/           duration formatting, date-range math, client-side aggregation
│   ├── test/            Vitest setup (jest-dom matchers)
│   ├── App.tsx           route table
│   └── main.tsx           entry point; imports design/tokens.css + index.css
├── eslint.config.js
├── .prettierrc.json
└── vite.config.ts        dev proxy + vitest config
```

## Scripts

```bash
npm run dev          # start the Vite dev server
npm run build         # tsc -b (type-check) then vite build
npm run lint          # eslint .
npm run format        # prettier --write .
npm run test          # vitest run (CI mode)
npm run test:watch    # vitest watch mode
```

## Notes on scope (Phase 1)

- **Month** reuses Week's shared components as-is (`EntryRow`, `SegmentedBreakdown`, `DayGroup`)
  over a calendar-month date range instead of a week; there's no dedicated backend endpoint for
  it — it fetches `GET /entries` with a month-range date filter and aggregates client-side
  (`src/utils/aggregate.ts`, `src/hooks/usePeriodEntries.ts`), same as Week.
- **Reports** and **Settings** nav items are present but disabled placeholders, reserved for a
  later phase.
- Tag creation is implicit: typing a tag name that doesn't exist yet and saving creates it
  server-side on save (`src/utils/resolveTagIds.ts`), per `design/screens.md` §1.3.
