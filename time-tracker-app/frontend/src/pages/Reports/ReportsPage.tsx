import { useEffect, useMemo, useState, type ReactElement } from "react";
import { getBackupExportUrl, getEntriesCsvExportUrl, getReportExportUrl } from "../../api/reports";
import { getSettings } from "../../api/settings";
import type { ExportFormat, ReportPeriod } from "../../api/types";
import { useReportSummary } from "../../hooks/useReportSummary";
import { SegmentedBreakdown } from "../../components/SegmentedBreakdown/SegmentedBreakdown";
import { MiniBarChart } from "../../components/MiniBarChart/MiniBarChart";
import { barsFromDays, barsFromWeeks } from "../../components/MiniBarChart/bars";
import {
  StackedCategoryChart,
  type StackedCategoryBucket,
  type StackedCategoryLegendItem,
} from "../../components/StackedCategoryChart/StackedCategoryChart";
import { CountLineChart, type CountLineChartPoint } from "../../components/CountLineChart/CountLineChart";
import { Skeleton } from "../../components/Skeleton/Skeleton";
import { formatDurationMinutes } from "../../utils/duration";
import type { BreakdownSegment } from "../../utils/aggregate";
import type { ReportBucketCategorySplit } from "../../api/types";
import styles from "./ReportsPage.module.css";

const PERIOD_OPTIONS: { value: ReportPeriod; label: string }[] = [
  { value: "week", label: "Week" },
  { value: "month", label: "Month" },
  { value: "quarter", label: "Quarter" },
];

const REPORT_EXPORT_OPTIONS: { value: "html" | "md" | "pdf"; label: string }[] = [
  { value: "html", label: "HTML" },
  { value: "md", label: "Markdown" },
  { value: "pdf", label: "PDF" },
];

/** Steps the anchor one whole period in `direction`, using calendar arithmetic on local date parts
 * rather than a fixed millisecond offset. A fixed offset is wrong three ways: a 30-day "month" step
 * back from Mar 31 lands on Mar 1 (same month — the button does nothing) and forward from Jan 31
 * skips February entirely; a 91-day "quarter" overshoots a 90-day Q1; and adding raw milliseconds
 * across a DST transition lands on 23:00 the previous local day, so `toIsoDate` reads a date one
 * off. Month/quarter normalize to the 1st, which also avoids JS month-overflow (`setMonth` on Jan 31
 * yields Mar 3). The backend re-expands whatever day it gets to the containing period. */
function stepAnchor(anchor: Date, period: ReportPeriod, direction: -1 | 1): Date {
  const year = anchor.getFullYear();
  const month = anchor.getMonth();
  if (period === "week") {
    const next = new Date(year, month, anchor.getDate());
    next.setDate(next.getDate() + 7 * direction);
    return next;
  }
  if (period === "month") {
    return new Date(year, month + direction, 1);
  }
  const quarterStartMonth = Math.floor(month / 3) * 3;
  return new Date(year, quarterStartMonth + 3 * direction, 1);
}

interface ZeroFilledDay {
  isoDate: string;
  minutes: number;
  entry_count: number;
  by_category: ReportBucketCategorySplit[];
}

/** Zero-fills every day in `[startDate, endDate]` (inclusive) with a report day's aggregates,
 * since `by_day` from the backend omits days with no entries but `MiniBarChart` (and the
 * category/count charts, which share its bucket list) expect a contiguous chronological run. */
function zeroFillDays(
  startDate: string,
  endDate: string,
  byDay: {
    date: string;
    total_minutes: number;
    entry_count: number;
    by_category: ReportBucketCategorySplit[];
  }[],
): ZeroFilledDay[] {
  const rowByDate = new Map(byDay.map((day) => [day.date, day]));
  const days: ZeroFilledDay[] = [];
  const cursor = new Date(`${startDate}T00:00:00`);
  const end = new Date(`${endDate}T00:00:00`);
  while (cursor <= end) {
    const year = cursor.getFullYear();
    const month = String(cursor.getMonth() + 1).padStart(2, "0");
    const day = String(cursor.getDate()).padStart(2, "0");
    const isoDate = `${year}-${month}-${day}`;
    const row = rowByDate.get(isoDate);
    days.push({
      isoDate,
      minutes: row?.total_minutes ?? 0,
      entry_count: row?.entry_count ?? 0,
      by_category: row?.by_category ?? [],
    });
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

function toIsoDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

/** Reports screen (Task 5, `design/screens.md` follow-on): period-based summary + rule-based
 * narrative, backed by `GET /reports/summary` and `GET /reports/narrative`. Unlike Week/Month, all
 * aggregation happens server-side — this page just renders the response and zero-fills `by_day`
 * for the mini bar chart. */
export function ReportsPage(): ReactElement {
  const [period, setPeriod] = useState<ReportPeriod>("week");
  const [dateAnchor, setDateAnchor] = useState<string | undefined>(undefined);
  const [defaultExportFormat, setDefaultExportFormat] = useState<ExportFormat>("html");
  const { summary, narrative, loading, error } = useReportSummary(period, dateAnchor);

  useEffect(() => {
    getSettings()
      .then((settings) => setDefaultExportFormat(settings.default_export_format))
      .catch(() => undefined);
  }, []);

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

  // Week reports bucket by day; Month/Quarter bucket by week (by_day is too sparse/wide to chart
  // at that granularity — same rationale as the exports, see `app/routers/exports.py`).
  const bucketedByWeek = summary !== null && summary.period !== "week";

  const chartBars = useMemo(() => {
    if (!summary) return [];
    if (summary.period === "week") {
      return barsFromDays(zeroFillDays(summary.start_date, summary.end_date, summary.by_day));
    }
    return barsFromWeeks(summary.by_week);
  }, [summary]);

  // Shared bucket list for `StackedCategoryChart`/`CountLineChart`, built once so both charts stay
  // in lockstep on bucket order and x-labels (week reports bucket by day; month/quarter bucket by
  // week, mirroring `chartBars`/`bucketedByWeek` above). Labels/titles are derived the same way
  // `MiniBarChart`'s bars are (`CW NN` + `formatWeekRangeShort`) so all three charts read as one
  // consistent x-axis.
  const categoryLegend = useMemo<StackedCategoryLegendItem[]>(() => {
    if (!summary) return [];
    return summary.by_category.map((row) => ({
      categoryId: row.category?.id ?? null,
      name: row.category ? row.category.name : "Uncategorized",
      color: row.category?.color ?? null,
    }));
  }, [summary]);

  const sharedBuckets = useMemo<{ stacked: StackedCategoryBucket[]; counts: CountLineChartPoint[] }>(() => {
    if (!summary) return { stacked: [], counts: [] };

    // Reuses `barsFromDays`/`barsFromWeeks` for labels/titles (same `CW NN` + date-range-title
    // convention as `MiniBarChart`'s own bars) rather than re-deriving them, zipped by index with
    // each row's `entry_count`/`by_category` — the two arrays are built from the same source list
    // in the same order, so they line up 1:1.
    const rows: { entry_count: number; by_category: ReportBucketCategorySplit[] }[] =
      summary.period === "week"
        ? zeroFillDays(summary.start_date, summary.end_date, summary.by_day)
        : summary.by_week;

    const stacked: StackedCategoryBucket[] = chartBars.map((bar, index) => ({
      key: bar.key,
      label: bar.label,
      ...(bar.title !== undefined && { title: bar.title }),
      segments: (rows[index]?.by_category ?? []).map((split) => ({
        categoryId: split.category_id,
        minutes: split.total_minutes,
      })),
    }));

    const counts: CountLineChartPoint[] = chartBars.map((bar, index) => ({
      key: bar.key,
      label: bar.label,
      ...(bar.title !== undefined && { title: bar.title }),
      count: rows[index]?.entry_count ?? 0,
    }));

    return { stacked, counts };
  }, [summary, chartBars]);

  function handlePagePeriod(direction: -1 | 1): void {
    const anchor = dateAnchor ? new Date(`${dateAnchor}T00:00:00`) : new Date();
    setDateAnchor(toIsoDate(stepAnchor(anchor, period, direction)));
  }

  function handleExportReport(format: "html" | "md" | "pdf"): void {
    window.open(getReportExportUrl(format, period, dateAnchor), "_blank", "noopener");
  }

  function handleExportCsv(): void {
    if (!summary) return;
    window.open(getEntriesCsvExportUrl(summary.start_date, summary.end_date), "_blank", "noopener");
  }

  function handleBackupDb(): void {
    window.open(getBackupExportUrl(), "_blank", "noopener");
  }

  const defaultReportFormat = defaultExportFormat === "csv" ? "html" : defaultExportFormat;
  const orderedExportOptions = [
    ...REPORT_EXPORT_OPTIONS.filter((option) => option.value === defaultReportFormat),
    ...REPORT_EXPORT_OPTIONS.filter((option) => option.value !== defaultReportFormat),
  ];

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
              Anchor date
            </label>
            <button
              type="button"
              aria-label={`Previous ${period}`}
              className={styles.dateAnchorNav}
              onClick={() => handlePagePeriod(-1)}
            >
              ‹
            </button>
            <input
              id="report-date-anchor"
              type="date"
              className={styles.dateAnchorInput}
              value={dateAnchor ?? ""}
              onChange={(event) => setDateAnchor(event.target.value || undefined)}
            />
            <button
              type="button"
              aria-label={`Next ${period}`}
              className={styles.dateAnchorNav}
              onClick={() => handlePagePeriod(1)}
            >
              ›
            </button>
            {dateAnchor && (
              <button
                type="button"
                className={styles.dateAnchorReset}
                onClick={() => setDateAnchor(undefined)}
                aria-label="Reset date to today"
              >
                Today
              </button>
            )}
          </div>
        </div>
      </header>
      <p className={styles.dateAnchorHint}>
        Any date in the {period} — the report expands to cover the whole {period} it falls in.
      </p>

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
                {orderedExportOptions.map((option) => (
                  <button key={option.value} type="button" onClick={() => handleExportReport(option.value)}>
                    Export {option.label}
                  </button>
                ))}
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

          {chartBars.length > 0 && (
            <div className={styles.chartCard}>
              <MiniBarChart bars={chartBars} labelEveryBar={bucketedByWeek} />
            </div>
          )}

          {sharedBuckets.stacked.length > 0 && (
            <div className={styles.chartCard}>
              <h2 className={styles.narrativeHeading}>Hours by category</h2>
              <StackedCategoryChart buckets={sharedBuckets.stacked} legend={categoryLegend} />
            </div>
          )}

          {sharedBuckets.counts.length > 0 && (
            <div className={styles.chartCard}>
              <h2 className={styles.narrativeHeading}>Entries per {bucketedByWeek ? "week" : "day"}</h2>
              <CountLineChart points={sharedBuckets.counts} />
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
