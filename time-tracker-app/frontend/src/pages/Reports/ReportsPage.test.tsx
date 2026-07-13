import { render, screen, fireEvent } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ReportsPage } from "./ReportsPage";
import { useReportSummary } from "../../hooks/useReportSummary";
import type { ReportNarrativeResponse, ReportSummaryResponse } from "../../api/types";

/**
 * `ReportsPage` renders whatever `useReportSummary` returns, plus wires the period
 * selector/export buttons — so the hook is mocked directly rather than the underlying API calls.
 */
vi.mock("../../hooks/useReportSummary", () => ({
  useReportSummary: vi.fn(),
}));

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
      { date: "2026-07-06", total_minutes: 90 },
      { date: "2026-07-07", total_minutes: 60 },
    ],
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
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders total time, entry count, category/tag breakdowns, chart and narrative", () => {
    mockHook();

    render(<ReportsPage />);

    expect(screen.getByText("2h 30m")).toBeInTheDocument();
    expect(screen.getByText("3 entries")).toBeInTheDocument();
    expect(screen.getByText("Deep Work")).toBeInTheDocument();
    expect(screen.getByText("Uncategorized")).toBeInTheDocument();
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
    mockHook({ summary: makeSummary({ entry_count: 0, total_minutes: 0, by_category: [], by_tag: [], by_day: [] }) });

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
});
