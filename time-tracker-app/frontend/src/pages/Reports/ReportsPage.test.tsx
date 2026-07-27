import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ReportsPage } from "./ReportsPage";
import { useReportSummary } from "../../hooks/useReportSummary";
import { getSettings } from "../../api/settings";
import type { ReportNarrativeResponse, ReportSummaryResponse, SettingsRead } from "../../api/types";

/**
 * `ReportsPage` renders whatever `useReportSummary` returns, plus wires the period
 * selector/export buttons — so the hook is mocked directly rather than the underlying API calls.
 */
vi.mock("../../hooks/useReportSummary", () => ({
  useReportSummary: vi.fn(),
}));

vi.mock("../../api/settings", () => ({
  getSettings: vi.fn(),
}));

function makeSettings(overrides: Partial<SettingsRead> = {}): SettingsRead {
  return {
    id: 1,
    default_entry_mode: "manual",
    week_starts_on: "monday",
    default_export_format: "html",
    database_label: "default",
    timezone: "UTC",
    ...overrides,
  };
}

function makeSummary(overrides: Partial<ReportSummaryResponse> = {}): ReportSummaryResponse {
  return {
    period: "week",
    start_date: "2026-07-06",
    end_date: "2026-07-12",
    timezone: "UTC",
    total_minutes: 150,
    entry_count: 3,
    by_category: [
      {
        category: { id: 1, name: "Deep Work", color: "blue", is_active: true, sort_order: 0 },
        total_minutes: 100,
        entry_count: 2,
      },
      { category: null, total_minutes: 50, entry_count: 1 },
    ],
    by_tag: [
      { tag: { id: 10, name: "focus", is_active: true }, total_minutes: 60, entry_count: 1 },
    ],
    by_day: [
      { date: "2026-07-06", total_minutes: 90, entry_count: 2, by_category: [] },
      { date: "2026-07-07", total_minutes: 60, entry_count: 1, by_category: [] },
    ],
    by_week: [],
    ...overrides,
  };
}

function makeNarrative(overrides: Partial<ReportNarrativeResponse> = {}): ReportNarrativeResponse {
  return {
    period: "week",
    start_date: "2026-07-06",
    end_date: "2026-07-12",
    timezone: "UTC",
    narrative: "You logged 2h 30m this week, mostly on Deep Work.",
    highlights: ["Most time went to Deep Work", "Busiest day was Monday"],
    ...overrides,
  };
}

function mockHook(overrides: Partial<ReturnType<typeof useReportSummary>> = {}): void {
  vi.mocked(useReportSummary).mockReturnValue({
    summary: makeSummary(),
    narrative: makeNarrative(),
    loading: false,
    error: null,
    reload: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  });
}

describe("ReportsPage", () => {
  beforeEach(() => {
    vi.mocked(getSettings).mockResolvedValue(makeSettings());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders total time, entry count, category/tag breakdowns, chart and narrative", () => {
    mockHook();

    render(<ReportsPage />);

    expect(screen.getByText("2h 30m")).toBeInTheDocument();
    expect(screen.getByText("3 entries")).toBeInTheDocument();
    // "Deep Work" appears both in the by-category breakdown and the new stacked chart's legend.
    expect(screen.getAllByText("Deep Work").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Uncategorized").length).toBeGreaterThan(0);
    expect(screen.getByText("#focus")).toBeInTheDocument();
    expect(screen.getByText("You logged 2h 30m this week, mostly on Deep Work.")).toBeInTheDocument();
    expect(screen.getByText("Most time went to Deep Work")).toBeInTheDocument();
    expect(screen.getByText("Busiest day was Monday")).toBeInTheDocument();
  });

  it("shows skeleton placeholders while loading", () => {
    mockHook({ loading: true, summary: null, narrative: null });

    const { container } = render(<ReportsPage />);

    expect(screen.queryByText("3 entries")).not.toBeInTheDocument();
    expect(container.querySelectorAll('[aria-hidden="true"]').length).toBeGreaterThan(0);
  });

  it("shows the empty-state message when the period has no entries", () => {
    mockHook({
      summary: makeSummary({ entry_count: 0, total_minutes: 0, by_category: [], by_tag: [], by_day: [], by_week: [] }),
    });

    render(<ReportsPage />);

    expect(screen.getByText("0m — nothing logged yet this period")).toBeInTheDocument();
  });

  it("triggers a refetch with the new period when clicking a different period option", () => {
    mockHook();
    render(<ReportsPage />);

    fireEvent.click(screen.getByRole("radio", { name: "Month" }));

    expect(useReportSummary).toHaveBeenLastCalledWith("month", undefined);
  });

  it("renders export buttons that open the correct export URLs", () => {
    mockHook();
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);

    render(<ReportsPage />);

    fireEvent.click(screen.getByText("Export HTML"));
    expect(openSpy).toHaveBeenCalledWith(
      "/api/exports/report.html?period=week",
      "_blank",
      "noopener",
    );

    fireEvent.click(screen.getByText("Export CSV"));
    expect(openSpy).toHaveBeenCalledWith(
      "/api/exports/entries.csv?start_date=2026-07-06&end_date=2026-07-12",
      "_blank",
      "noopener",
    );

    fireEvent.click(screen.getByText("Backup DB"));
    expect(openSpy).toHaveBeenCalledWith("/api/exports/backup", "_blank", "noopener");
  });

  it("charts by_day (zero-filled) for the week period", () => {
    mockHook({
      summary: makeSummary({
        period: "week",
        start_date: "2026-07-06",
        end_date: "2026-07-12",
        by_day: [{ date: "2026-07-06", total_minutes: 90, entry_count: 2, by_category: [] }],
        by_week: [
          {
            week_start: "2026-06-29",
            week_end: "2026-07-05",
            total_minutes: 999,
            entry_count: 9,
            by_category: [],
          },
        ],
      }),
    });

    render(<ReportsPage />);

    // Every weekday in the range is labeled, including days absent from `by_day` (zero-filled).
    // Labeled by both `StackedCategoryChart` and `CountLineChart`, hence `getAllByText`.
    for (const label of ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
    // The by_week data is ignored for the week period.
    expect(screen.queryByText("Jun 29 – Jul 5")).not.toBeInTheDocument();
  });

  it("charts by_week for the month period", () => {
    mockHook({
      summary: makeSummary({
        period: "month",
        start_date: "2026-06-01",
        end_date: "2026-06-30",
        by_week: [
          {
            week_start: "2026-06-01",
            week_end: "2026-06-07",
            total_minutes: 120,
            entry_count: 3,
            by_category: [],
          },
          {
            week_start: "2026-06-08",
            week_end: "2026-06-14",
            total_minutes: 60,
            entry_count: 1,
            by_category: [],
          },
        ],
      }),
    });

    render(<ReportsPage />);

    expect(screen.getAllByText("CW 23").length).toBeGreaterThan(0);
    expect(screen.getAllByText("CW 24").length).toBeGreaterThan(0);
  });

  it("renders exactly two chart cards (Hours by category + Entries per day/week), no neutral MiniBarChart card", () => {
    mockHook({
      summary: makeSummary({
        period: "week",
        start_date: "2026-07-06",
        end_date: "2026-07-12",
        by_day: [{ date: "2026-07-06", total_minutes: 90, entry_count: 2, by_category: [] }],
      }),
      narrative: null,
    });

    render(<ReportsPage />);

    expect(screen.getByText("Hours by category")).toBeInTheDocument();
    expect(screen.getByText("Entries per day")).toBeInTheDocument();
    // Two `<h2 class="narrativeHeading">` chart titles plus the narrative's own "Summary" heading
    // would make three; without a narrative response here, exactly these two chart headings exist.
    expect(screen.getAllByRole("heading", { level: 2 })).toHaveLength(2);
  });

  it("charts by_week for the quarter period", () => {
    mockHook({
      summary: makeSummary({
        period: "quarter",
        start_date: "2026-04-01",
        end_date: "2026-06-30",
        by_week: [
          {
            week_start: "2026-06-29",
            week_end: "2026-07-05",
            total_minutes: 45,
            entry_count: 1,
            by_category: [],
          },
        ],
      }),
    });

    render(<ReportsPage />);

    expect(screen.getAllByText("CW 27").length).toBeGreaterThan(0);
  });

  it("surfaces the export option matching settings.default_export_format first (md)", async () => {
    vi.mocked(getSettings).mockResolvedValue(makeSettings({ default_export_format: "md" }));
    mockHook();

    render(<ReportsPage />);

    await waitFor(() => {
      const buttons = screen.getAllByRole("button", { name: /^Export /i }).map((btn) => btn.textContent);
      expect(buttons[0]).toBe("Export Markdown");
    });
  });

  it("surfaces the export option matching settings.default_export_format first (pdf)", async () => {
    vi.mocked(getSettings).mockResolvedValue(makeSettings({ default_export_format: "pdf" }));
    mockHook();

    render(<ReportsPage />);

    await waitFor(() => {
      const buttons = screen.getAllByRole("button", { name: /^Export /i }).map((btn) => btn.textContent);
      expect(buttons[0]).toBe("Export PDF");
    });
  });

  it("falls back to HTML first when the default export format is csv (not a report format)", async () => {
    vi.mocked(getSettings).mockResolvedValue(makeSettings({ default_export_format: "csv" }));
    mockHook();

    render(<ReportsPage />);

    await waitFor(() => {
      const buttons = screen.getAllByRole("button", { name: /^Export /i }).map((btn) => btn.textContent);
      expect(buttons[0]).toBe("Export HTML");
    });
  });

  it("labels the date field as an anchor with a hint, and offers paging plus a Today reset", () => {
    mockHook();
    render(<ReportsPage />);

    expect(screen.getByLabelText("Anchor date")).toBeInTheDocument();
    expect(
      screen.getByText("Any date in the week — the report expands to cover the whole week it falls in."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous week" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next week" })).toBeInTheDocument();
    // No anchor set yet, so there's nothing to reset.
    expect(screen.queryByRole("button", { name: "Reset date to today" })).not.toBeInTheDocument();
  });

  it("shows a Today reset button once an anchor is set, and it clears the anchor", () => {
    mockHook();
    render(<ReportsPage />);

    fireEvent.change(screen.getByLabelText("Anchor date"), { target: { value: "2026-07-08" } });
    expect(useReportSummary).toHaveBeenLastCalledWith("week", "2026-07-08");

    fireEvent.click(screen.getByRole("button", { name: "Reset date to today" }));
    expect(useReportSummary).toHaveBeenLastCalledWith("week", undefined);
  });

  describe("stepAnchor (‹ / › paging)", () => {
    it("weeks back/forward by exactly 7 local days, preserving day-of-week", () => {
      mockHook();
      render(<ReportsPage />);

      fireEvent.change(screen.getByLabelText("Anchor date"), { target: { value: "2026-07-08" } });
      fireEvent.click(screen.getByRole("button", { name: "Next week" }));

      expect(useReportSummary).toHaveBeenLastCalledWith("week", "2026-07-15");
    });

    it("months back from Mar 31 lands in February (not the same month)", () => {
      mockHook();
      render(<ReportsPage />);

      fireEvent.click(screen.getByRole("radio", { name: "Month" }));
      fireEvent.change(screen.getByLabelText("Anchor date"), { target: { value: "2026-03-31" } });
      fireEvent.click(screen.getByRole("button", { name: "Previous month" }));

      expect(useReportSummary).toHaveBeenLastCalledWith("month", "2026-02-01");
    });

    it("months forward from Jan 31 lands in February (not March)", () => {
      mockHook();
      render(<ReportsPage />);

      fireEvent.click(screen.getByRole("radio", { name: "Month" }));
      fireEvent.change(screen.getByLabelText("Anchor date"), { target: { value: "2026-01-31" } });
      fireEvent.click(screen.getByRole("button", { name: "Next month" }));

      expect(useReportSummary).toHaveBeenLastCalledWith("month", "2026-02-01");
    });

    it("quarters back from Mar 31 (Q1) lands in Q4 2025", () => {
      mockHook();
      render(<ReportsPage />);

      fireEvent.click(screen.getByRole("radio", { name: "Quarter" }));
      fireEvent.change(screen.getByLabelText("Anchor date"), { target: { value: "2026-03-31" } });
      fireEvent.click(screen.getByRole("button", { name: "Previous quarter" }));

      expect(useReportSummary).toHaveBeenLastCalledWith("quarter", "2025-10-01");
    });

    it("quarters forward from Jan 15 (Q1) lands in Q2 2026", () => {
      mockHook();
      render(<ReportsPage />);

      fireEvent.click(screen.getByRole("radio", { name: "Quarter" }));
      fireEvent.change(screen.getByLabelText("Anchor date"), { target: { value: "2026-01-15" } });
      fireEvent.click(screen.getByRole("button", { name: "Next quarter" }));

      expect(useReportSummary).toHaveBeenLastCalledWith("quarter", "2026-04-01");
    });
  });
});
