import { API_PREFIX, apiRequest } from "./client";
import type { ReportNarrativeResponse, ReportPeriod, ReportSummaryResponse } from "./types";

export function getReportSummary(period: ReportPeriod, date?: string): Promise<ReportSummaryResponse> {
  return apiRequest<ReportSummaryResponse>("/reports/summary", { query: { period, date } });
}

export function getReportNarrative(period: ReportPeriod, date?: string): Promise<ReportNarrativeResponse> {
  return apiRequest<ReportNarrativeResponse>("/reports/narrative", { query: { period, date } });
}

/**
 * Export downloads are plain browser file downloads, not JSON — they're triggered via `window.open`
 * / anchor clicks in the page rather than through `apiRequest` (which always JSON-parses the
 * response body). These helpers just build the query-scoped URL strings.
 */
export function getReportHtmlExportUrl(period: ReportPeriod, date?: string): string {
  const params = new URLSearchParams({ period });
  if (date) params.set("date", date);
  return `${API_PREFIX}/exports/report.html?${params.toString()}`;
}

export function getEntriesCsvExportUrl(startDate: string, endDate: string): string {
  const params = new URLSearchParams({ start_date: startDate, end_date: endDate });
  return `${API_PREFIX}/exports/entries.csv?${params.toString()}`;
}

export function getBackupExportUrl(): string {
  return `${API_PREFIX}/exports/backup`;
}
