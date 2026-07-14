import { useCallback, useEffect, useRef, useState } from "react";
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
  const mountedRef = useRef(true);

  const reload = useCallback(async () => {
    setError(null);
    const [summaryResponse, narrativeResponse] = await Promise.all([
      getReportSummary(period, date),
      getReportNarrative(period, date),
    ]);
    if (!mountedRef.current) return;
    setSummary(summaryResponse);
    setNarrative(narrativeResponse);
  }, [period, date]);

  useEffect(() => {
    mountedRef.current = true;
    setLoading(true);
    reload()
      .catch((err) => {
        if (mountedRef.current) setError(err instanceof Error ? err.message : "Failed to load report.");
      })
      .finally(() => {
        if (mountedRef.current) setLoading(false);
      });
    return () => {
      mountedRef.current = false;
    };
  }, [reload]);

  return { summary, narrative, loading, error, reload };
}
