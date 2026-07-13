import { useCallback, useEffect, useState } from "react";
import { getReportNarrative, getReportSummary } from "../api/reports";
import type { ReportNarrativeResponse, ReportPeriod, ReportSummaryResponse } from "../api/types";

/** Fetches both `GET /reports/summary` and `GET /reports/narrative` in parallel for the given
 * period/date anchor. Mirrors `usePeriodEntries`'s cancelled-guard + loading/error handling. */
export function useReportSummary(
  period: ReportPeriod,
  date?: string,
): {
  summary: ReportSummaryResponse | null;
  narrative: ReportNarrativeResponse | null;
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
} {
  const [summary, setSummary] = useState<ReportSummaryResponse | null>(null);
  const [narrative, setNarrative] = useState<ReportNarrativeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setError(null);
    const [summaryResponse, narrativeResponse] = await Promise.all([
      getReportSummary(period, date),
      getReportNarrative(period, date),
    ]);
    setSummary(summaryResponse);
    setNarrative(narrativeResponse);
  }, [period, date]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    reload()
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load report.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [reload]);

  return { summary, narrative, loading, error, reload };
}
