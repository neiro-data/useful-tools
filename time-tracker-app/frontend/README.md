# Time Tracker — Frontend

## Resume

This is the React single-page application of the Time Tracker App. It shows the Today, Week,
Month, Reports and Settings screens. It calls the FastAPI backend in `../app`. It uses the design
system in `../design`. The parent project is [`../README.md`](../README.md).

- **Stack:** Vite, React 19, TypeScript in strict mode, and `react-router-dom` for the routes.
- **Entry point:** `src/main.tsx`. It mounts `src/App.tsx` inside a `BrowserRouter`.
- **Design:** `src/main.tsx` imports `../../design/tokens.css`. Every colour comes from a
  `var(--...)` token. The theme follows `prefers-color-scheme`. There is no manual toggle. See
  [`../design/DESIGN_SYSTEM.md`](../design/DESIGN_SYSTEM.md) §5.4.
- **API contract:** `src/api/` is a typed client for
  [`../app/API_CONTRACT.md`](../app/API_CONTRACT.md) and `../app/schemas.py`.
- **Host requirements:** Node.js and npm. The backend must run at the same time.

## Agent read

If you are an AI agent, read also [README_AGENT.md](README_AGENT.md).

## Quick start

The application has two halves. Both must run.

1. Start the backend from the parent directory `time-tracker-app/`.

   ```bash
   uv sync
   uv run uvicorn app.main:app --reload
   ```

   The API answers at `http://127.0.0.1:8000`.

2. Start the frontend from this directory.

   ```bash
   npm install
   npm run dev
   ```

   The interface answers at `http://localhost:5173`.

The dev server sends every `/api/*` request to the backend origin. The application calls relative
paths only, so there is no CORS configuration to keep in step. For the other commands, the proxy
override and the production build, see [scripts-guide.md](scripts-guide.md).

## Screens

`src/App.tsx` holds the route table. The path `/` and any unknown path redirect to `/today`. The
left navigation rail is `src/components/AppShell/AppShell.tsx`. All five screens are built.

| Route | Page | Content |
| --- | --- | --- |
| `/today` | `src/pages/Today/TodayPage.tsx` | The live timer, the quick-add card and today's entries. |
| `/week` | `src/pages/Week/WeekPage.tsx` | One calendar week, grouped per day, with a category and tag breakdown. |
| `/month` | `src/pages/Month/MonthPage.tsx` | One calendar month, with the same components as Week. |
| `/reports` | `src/pages/Reports/ReportsPage.tsx` | A week, month or quarter summary, its charts and its exports. |
| `/settings` | `src/pages/Settings/SettingsPage.tsx` | The default entry mode, the week start, the export format, the timezone and the categories. |

The Reports screen exports a report as HTML, Markdown or PDF. It also exports the entries as CSV
and the database as a backup. The wireframes are in
[`../design/screens.md`](../design/screens.md).

## API client

`src/api/` holds one module per resource: `categories`, `entries`, `reports`, `settings`, `tags`,
`timer` and `today`. Each module calls the shared `apiRequest()` wrapper in `src/api/client.ts`.
`src/api/types.ts` mirrors `../app/schemas.py`.

`apiRequest()` turns every non-2xx response into one `ApiError` (`src/api/errors.ts`). The error
carries the stable `code`, the readable `message` and the structured `details` of the backend
envelope. A network failure gives the code `network_error`. Call sites branch on `error.code`.
For the code example and the conflict flow, see
[README_AGENT.md — Error envelope](README_AGENT.md#error-envelope).

## Data model

This package creates no database. The single SQLite file belongs to the backend. For the tables,
the views and the columns, see [`../SCHEMA.md`](../SCHEMA.md). For the HTTP shapes, see
[`../app/API_CONTRACT.md`](../app/API_CONTRACT.md).

## Layout

```
frontend/
├── src/
│   ├── api/            typed API client: client.ts, errors.ts, types.ts, 7 resource modules
│   ├── components/     16 shared components: AppShell, EntryRow, TimerWidget, DayGroup,
│   │                    SegmentedBreakdown, MiniBarChart, StackedCategoryChart, CountLineChart,
│   │                    CategoryChip, CategoryPicker, TagChip, DateTimePicker, ManualEntryForm,
│   │                    RecentChipsRail, TimerBanner, Skeleton
│   ├── hooks/          7 hooks: useCategories, useLiveTimer, usePeriodEntries, useReportSummary,
│   │                    useRunningTimer, useSettings, useTimezones
│   ├── pages/          Today, Week, Month, Reports, Settings
│   ├── utils/          aggregate, categoryColor, dateRange, duration, recentTags, resolveTagIds,
│   │                    timeRange
│   ├── test/           the Vitest setup, with the jest-dom matchers
│   ├── App.tsx         the route table
│   ├── main.tsx        the entry point; imports ../../design/tokens.css and ./index.css
│   ├── index.css       the global stylesheet
│   └── vite-env.d.ts   the Vite client types
├── dist/               the build output; git ignores it
├── index.html          the Vite HTML entry point
├── vite.config.ts      the dev proxy, the fs allow list and the Vitest configuration
├── eslint.config.js    the ESLint configuration
├── .prettierrc.json    the Prettier configuration
├── tsconfig.json       the project references
├── tsconfig.app.json   the strict compiler options for src/
├── tsconfig.node.json  the compiler options for vite.config.ts
├── README.md           this file: what the package is, and the first run
├── scripts-guide.md    every command, the proxy override and the production build
└── README_AGENT.md     the notes for an AI agent: contracts, decisions and drift
```
