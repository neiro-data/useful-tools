import { describe, expect, it, vi } from "vitest";
import { apiRequest } from "./client";
import {
  getBackupExportUrl,
  getEntriesCsvExportUrl,
  getReportHtmlExportUrl,
  getReportNarrative,
  getReportSummary,
} from "./reports";

/**
 * `api/reports.ts` tests: `getReportSummary`/`getReportNarrative` just delegate to `apiRequest`
 * with the right path/query, so `apiRequest` is mocked (no real fetch). The export URL builders
 * are pure string builders and are asserted directly against their `/api/exports/...` output.
 */
vi.mock("./client", () => ({
  apiRequest: vi.fn(),
  API_PREFIX: "/api",
}));

describe("getReportSummary", () => {
  it("calls apiRequest with the summary path and period query", async () => {
    vi.mocked(apiRequest).mockResolvedValue({ period: "week" });

    await getReportSummary("week");

    expect(apiRequest).toHaveBeenCalledWith("/reports/summary", {
      query: { period: "week", date: undefined },
    });
  });

  it("passes the date anchor through when provided", async () => {
    vi.mocked(apiRequest).mockResolvedValue({ period: "month" });

    await getReportSummary("month", "2026-07-01");

    expect(apiRequest).toHaveBeenCalledWith("/reports/summary", {
      query: { period: "month", date: "2026-07-01" },
    });
  });
});

describe("getReportNarrative", () => {
  it("calls apiRequest with the narrative path and period query", async () => {
    vi.mocked(apiRequest).mockResolvedValue({ period: "quarter" });

    await getReportNarrative("quarter");

    expect(apiRequest).toHaveBeenCalledWith("/reports/narrative", {
      query: { period: "quarter", date: undefined },
    });
  });

  it("passes the date anchor through when provided", async () => {
    vi.mocked(apiRequest).mockResolvedValue({ period: "week" });

    await getReportNarrative("week", "2026-07-13");

    expect(apiRequest).toHaveBeenCalledWith("/reports/narrative", {
      query: { period: "week", date: "2026-07-13" },
    });
  });
});

describe("getReportHtmlExportUrl", () => {
  it("builds the export URL with just the period when no date anchor is given", () => {
    expect(getReportHtmlExportUrl("week")).toBe("/api/exports/report.html?period=week");
  });

  it("includes the date anchor when provided", () => {
    expect(getReportHtmlExportUrl("month", "2026-07-01")).toBe(
      "/api/exports/report.html?period=month&date=2026-07-01",
    );
  });
});

describe("getEntriesCsvExportUrl", () => {
  it("builds the export URL with start_date and end_date", () => {
    expect(getEntriesCsvExportUrl("2026-07-01", "2026-07-31")).toBe(
      "/api/exports/entries.csv?start_date=2026-07-01&end_date=2026-07-31",
    );
  });
});

describe("getBackupExportUrl", () => {
  it("returns the fixed backup export path", () => {
    expect(getBackupExportUrl()).toBe("/api/exports/backup");
  });
});
