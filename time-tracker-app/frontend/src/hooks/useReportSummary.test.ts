import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useReportSummary } from "./useReportSummary";
import { getReportNarrative, getReportSummary } from "../api/reports";
import type { ReportNarrativeResponse, ReportSummaryResponse } from "../api/types";

/**
 * `useReportSummary` fetches `GET /reports/summary` and `GET /reports/narrative` in parallel for
 * a period/date anchor. The `../api/reports` module is mocked so no real fetch happens.
 */
vi.mock("../api/reports", () => ({
  getReportSummary: vi.fn(),
  getReportNarrative: vi.fn(),
}));

function makeSummary(overrides: Partial<ReportSummaryResponse> = {}): ReportSummaryResponse {
  return {
    period: "week",
    start_date: "2026-07-06",
    end_date: "2026-07-12",
    timezone: "UTC",
    total_minutes: 120,
    entry_count: 2,
    by_category: [],
    by_tag: [],
    by_day: [],
    ...overrides,
  };
}

function makeNarrative(overrides: Partial<ReportNarrativeResponse> = {}): ReportNarrativeResponse {
  return {
    period: "week",
    start_date: "2026-07-06",
    end_date: "2026-07-12",
    timezone: "UTC",
    narrative: "You logged 2 hours this week.",
    highlights: ["Most time went to Deep Work"],
    ...overrides,
  };
}

describe("useReportSummary", () => {
  it("fetches summary + narrative for the given period and resolves loading with no error", async () => {
    const summary = makeSummary();
    const narrative = makeNarrative();
    vi.mocked(getReportSummary).mockResolvedValue(summary);
    vi.mocked(getReportNarrative).mockResolvedValue(narrative);

    const { result } = renderHook(() => useReportSummary("week"));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.summary).toEqual(summary);
    expect(result.current.narrative).toEqual(narrative);
    expect(result.current.error).toBeNull();
    expect(getReportSummary).toHaveBeenCalledWith("week", undefined);
    expect(getReportNarrative).toHaveBeenCalledWith("week", undefined);
  });

  it("passes the date anchor through to both API calls", async () => {
    vi.mocked(getReportSummary).mockResolvedValue(makeSummary());
    vi.mocked(getReportNarrative).mockResolvedValue(makeNarrative());

    const { result } = renderHook(() => useReportSummary("month", "2026-07-01"));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(getReportSummary).toHaveBeenCalledWith("month", "2026-07-01");
    expect(getReportNarrative).toHaveBeenCalledWith("month", "2026-07-01");
  });

  it("sets error and stops loading when a request rejects", async () => {
    vi.mocked(getReportSummary).mockRejectedValue(new Error("Network down"));
    vi.mocked(getReportNarrative).mockResolvedValue(makeNarrative());

    const { result } = renderHook(() => useReportSummary("week"));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe("Network down");
  });
});
