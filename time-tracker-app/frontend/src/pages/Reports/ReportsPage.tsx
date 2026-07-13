import { useMemo, useState, type ReactElement } from "react";
import { getBackupExportUrl, getEntriesCsvExportUrl, getReportHtmlExportUrl } from "../../api/reports";
import type { ReportPeriod } from "../../api/types";
import { useReportSummary } from "../../hooks/useReportSummary";
import { SegmentedBreakdown } from "../../components/SegmentedBreakdown/SegmentedBreakdown";
import { MiniBarChart } from "../../components/MiniBarChart/MiniBarChart";
import { Skeleton } from "../../components/Skeleton/Skeleton";
import { formatDurationMinutes } from "../../utils/duration";
import type { BreakdownSegment } from "../../utils/aggregate";
import styles from "./ReportsPage.module.css";

const PERIOD_OPTIONS: { value: ReportPeriod; label: string }[] = [
  { value: "week", label: "Week" },
  { value: "month", label: "Month" },
  { value: "quarter", label: "Quarter" },
];

/** Zero-fills every day in `[startDate, endDate]` (inclusive) with a report day's minutes, since
 * `by_day` from the backend omits days with no entries but `MiniBarChart` expects a contiguous
 * chronological run. */
function zeroFillDays(
  startDate: string,
  endDate: string,
  byDay: { date: string; total_minutes: number }[],
): { isoDate: string; minutes: number }[] {
  const minutesByDate = new Map(byDay.map((day) => [day.date, day.total_minutes]));
  const days: { isoDate: string; minutes: number }[] = [];
  const cursor = new Date(`${startDate}T00:00:00`);
  const end = new Date(`${endDate}T00:00:00`);
  while (cursor <= end) {
    const year = cursor.getFullYear();
    const month = String(cursor.getMonth() + 1).padStart(2, "0");
    const day = String(cursor.getDate()).padStart(2, "0");
    const isoDate = `${year}-${month}-${day}`;
    days.push({ isoDate, minutes: minutesByDate.get(isoDate) ?? 0 });
    cursor.setDate(cursor.getDate() + 1);
  }
  return days;
}

function formatDateRange(startDate: string, endDate: string): string {
  const start = new Date(`${startDate}T00:00:00`);
  const end = new Date(`${endDate}T00:00:00`);
  const startLabel = start.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  const endLabel = end.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
  return `${startLabel} – ${endLabel}`;
}

/** Reports screen (Task 5, `design/screens.md` follow-on): period-based summary + rule-based
 * narrative, backed by `GET /reports/summary` and `GET /reports/narrative`. Unlike Week/Month, all
 * aggregation happens server-side — this page just renders the response and zero-fills `by_day`
 * for the mini bar chart. */
export function ReportsPage(): ReactElement {
  const [period, setPeriod] = useState<ReportPeriod>("week");
  const [dateAnchor, setDateAnchor] = useState<string | undefined>(undefined);
  const { summary, narrative, loading, error } = useReportSummary(period, dateAnchor);

  const categoryBreakdown = useMemo<BreakdownSegment[]>(() => {
    if (!summary) return [];
    const total = summary.by_category.reduce((sum, row) => sum + row.total_minutes, 0);
    return summary.by_category.map((row) => ({
      key: row.category ? `cat-${row.category.id}` : "uncategorized",
      label: row.category ? row.category.name : "Uncategorized",
      colorKey: row.category?.color ?? "slate",
      minutes: row.total_minutes,
      percent: total > 0 ? (row.total_minutes / total) * 100 : 0,
    }));
  }, [summary]);

  const tagBreakdown = useMemo<BreakdownSegment[]>(() => {
    if (!summary) return [];
    const total = summary.by_tag.reduce((sum, row) => sum + row.total_minutes, 0);
    return summary.by_tag.map((row) => ({
      key: `tag-${row.tag.id}`,
      label: `#${row.tag.name}`,
      colorKey: null,
      minutes: row.total_minutes,
      percent: total > 0 ? (row.total_minutes / total) * 100 : 0,
    }));
  }, [summary]);

  const chartDays = useMemo(() => {
    if (!summary) return [];
    return zeroFillDays(summary.start_date, summary.end_date, summary.by_day);
  }, [summary]);

  function handleExportHtml(): void {
    window.open(getReportHtmlExportUrl(period, dateAnchor), "_blank", "noopener");
  }

  function handleExportCsv(): void {
    if (!summary) return;
    window.open(getEntriesCsvExportUrl(summary.start_date, summary.end_date), "_blank", "noopener");
  }

  function handleBackupDb(): void {
    window.open(getBackupExportUrl(), "_blank", "noopener");
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.title}>Reports</h1>
        <div className={styles.headerControls}>
          <div className={styles.periodSelector} role="radiogroup" aria-label="Report period">
            {PERIOD_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                role="radio"
                aria-checked={period === option.value}
                className={`${styles.periodButton} ${period === option.value ? styles.periodButtonActive : ""}`}
                onClick={() => setPeriod(option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>
          <div className={styles.dateAnchor}>
            <label htmlFor="report-date-anchor" className={styles.dateAnchorLabel}>
              Date
            </label>
            <input
              id="report-date-anchor"
              type="date"
              className={styles.dateAnchorInput}
              value={dateAnchor ?? ""}
              onChange={(event) => setDateAnchor(event.target.value || undefined)}
            />
            {dateAnchor && (
              <button
                type="button"
                className={styles.dateAnchorReset}
                onClick={() => setDateAnchor(undefined)}
              >
                Today
              </button>
            )}
          </div>
        </div>
      </header>

      {error && (
        <div className={styles.errorBanner} role="alert">
          {error}
        </div>
      )}

      {loading ? (
        <div className={styles.summaryGrid}>
          <Skeleton height={140} />
          <Skeleton height={140} />
        </div>
      ) : summary ? (
        <>
          <div className={styles.summaryGrid}>
            <div className={styles.summaryCard}>
              <p className={styles.rangeLabel}>{formatDateRange(summary.start_date, summary.end_date)}</p>
              <p className={styles.totalLabel}>Total time</p>
              <p className={styles.totalValue}>
                {summary.entry_count === 0
                  ? "0m — nothing logged yet this period"
                  : formatDurationMinutes(summary.total_minutes)}
              </p>
              <p className={styles.entryCount}>
                {summary.entry_count} {summary.entry_count === 1 ? "entry" : "entries"}
              </p>
              <div className={styles.exportActions}>
                <button type="button" onClick={handleExportHtml}>
                  Export HTML
                </button>
                <button type="button" onClick={handleExportCsv}>
                  Export CSV
                </button>
                <button type="button" onClick={handleBackupDb}>
                  Backup DB
                </button>
              </div>
            </div>
            <div className={styles.breakdownCard}>
              <SegmentedBreakdown title="By category" segments={categoryBreakdown} variant="category" />
              <SegmentedBreakdown title="By tag" segments={tagBreakdown} variant="tag" visibleLimit={5} />
            </div>
          </div>

          {chartDays.length > 0 && (
            <div className={styles.chartCard}>
              <MiniBarChart days={chartDays} />
            </div>
          )}

          {narrative && (
            <div className={styles.narrativeCard}>
              <h2 className={styles.narrativeHeading}>Summary</h2>
              <p className={styles.narrativeText}>{narrative.narrative}</p>
              {narrative.highlights.length > 0 && (
                <ul className={styles.highlightsList}>
                  {narrative.highlights.map((highlight) => (
                    <li key={highlight}>{highlight}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </>
      ) : null}
    </div>
  );
}
