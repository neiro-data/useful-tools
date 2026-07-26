import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MonthPage } from "./MonthPage";
import { usePeriodEntries } from "../../hooks/usePeriodEntries";
import { useRunningTimer } from "../../hooks/useRunningTimer";
import { listCategories } from "../../api/categories";
import { listTags } from "../../api/tags";
import styles from "../../components/MiniBarChart/MiniBarChart.module.css";
import monthStyles from "./MonthPage.module.css";
import type { CategoryRead, EntryRead } from "../../api/types";

/**
 * `MonthPage` renders whatever `usePeriodEntries`/`useRunningTimer` return and aggregates
 * client-side — so the hooks (and the categories/tags list calls) are mocked directly, mirroring
 * `ReportsPage.test.tsx`'s convention of mocking the data-fetching layer rather than the network.
 */
vi.mock("../../hooks/usePeriodEntries", () => ({
  usePeriodEntries: vi.fn(),
}));
vi.mock("../../hooks/useRunningTimer", () => ({
  useRunningTimer: vi.fn(),
}));
vi.mock("../../api/categories", () => ({
  listCategories: vi.fn(),
}));
vi.mock("../../api/tags", () => ({
  listTags: vi.fn(),
}));

const deepWork: CategoryRead = { id: 1, name: "Deep Work", color: "blue", is_active: true, sort_order: 0 };

function makeEntry(overrides: Partial<EntryRead>): EntryRead {
  return {
    id: 1,
    title: "Entry",
    notes: null,
    category: deepWork,
    tags: [],
    start_ts: "2026-06-01T09:00:00+00:00",
    end_ts: "2026-06-01T10:00:00+00:00",
    duration_minutes: 60,
    entry_mode: "manual",
    created_at: "2026-06-01T09:00:00+00:00",
    updated_at: "2026-06-01T09:00:00+00:00",
    ...overrides,
  };
}

function mockHooks(entries: EntryRead[]): void {
  vi.mocked(usePeriodEntries).mockReturnValue({
    entries,
    loading: false,
    error: null,
    reload: vi.fn().mockResolvedValue(undefined),
  });
  vi.mocked(useRunningTimer).mockReturnValue({
    runningTimer: null,
    loading: false,
    refresh: vi.fn().mockResolvedValue(undefined),
    stop: vi.fn().mockResolvedValue(undefined),
  });
  vi.mocked(listCategories).mockResolvedValue({ items: [], total: 0 });
  vi.mocked(listTags).mockResolvedValue({ items: [], total: 0 });
}

describe("MonthPage", () => {
  beforeEach(() => {
    // Fix "today" to a stable date inside June 2026 so `getMonthRange(new Date(), 0)` resolves
    // deterministically without paging.
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 5, 15, 12, 0, 0));
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("renders a weekly mini bar chart (bucketed by week, not by day)", () => {
    const entries = [
      makeEntry({ id: 1, start_ts: "2026-06-01T09:00:00+00:00", duration_minutes: 60 }),
      makeEntry({ id: 2, start_ts: "2026-06-10T09:00:00+00:00", duration_minutes: 30 }),
      makeEntry({ id: 3, start_ts: "2026-06-30T09:00:00+00:00", duration_minutes: 45 }),
    ];
    mockHooks(entries);

    const { container } = render(<MonthPage />);

    const chart = container.querySelector(`.${styles.chart}`);
    expect(chart).toBeInTheDocument();

    const columns = chart?.querySelectorAll(`.${styles.column}`) ?? [];
    // June 2026 has 30 days but only a handful of Monday-start weeks — bucketed by week, not day.
    expect(columns.length).toBeGreaterThan(0);
    expect(columns.length).toBeLessThan(10);

    // Weekly labels look like date ranges (contain an en dash), not single weekday names.
    const labels = [...(chart?.querySelectorAll(`.${styles.label}`) ?? [])].map((el) => el.textContent);
    for (const label of labels) {
      expect(label).toMatch(/–/);
    }
    for (const weekday of ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]) {
      expect(screen.queryByText(weekday)).not.toBeInTheDocument();
    }
  });

  it("sums the chart's bucket minutes to the month's total", () => {
    const entries = [
      makeEntry({ id: 1, start_ts: "2026-06-01T09:00:00+00:00", duration_minutes: 60 }),
      makeEntry({ id: 2, start_ts: "2026-06-10T09:00:00+00:00", duration_minutes: 30 }),
    ];
    mockHooks(entries);

    const { container } = render(<MonthPage />);

    const totalValue = container.querySelector(`.${monthStyles.totalValue}`);
    expect(totalValue?.textContent).toBe("1h 30m");
  });
});
