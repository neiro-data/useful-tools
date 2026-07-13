import { useEffect, useMemo, useState, type ReactElement } from "react";
import { createEntry, deleteEntry, updateEntry } from "../../api/entries";
import { listCategories } from "../../api/categories";
import { listTags } from "../../api/tags";
import type { CategoryRead, TagRead } from "../../api/types";
import { usePeriodEntries } from "../../hooks/usePeriodEntries";
import { useRunningTimer } from "../../hooks/useRunningTimer";
import { DayGroup } from "../../components/DayGroup/DayGroup";
import { SegmentedBreakdown } from "../../components/SegmentedBreakdown/SegmentedBreakdown";
import { TimerBanner } from "../../components/TimerBanner/TimerBanner";
import { Skeleton } from "../../components/Skeleton/Skeleton";
import { getMonthRange, enumerateDays, formatMonthHeading, isToday } from "../../utils/dateRange";
import { breakdownByCategory, breakdownByTag, groupByDay, totalMinutes } from "../../utils/aggregate";
import { formatDurationMinutes } from "../../utils/duration";
import type { EntryRowSaveValues } from "../../components/EntryRow/EntryRow";
import styles from "./MonthPage.module.css";

/**
 * Month screen: the same day-grouping, entry-row, and by-category/by-tag breakdown components as
 * Week, applied over the current calendar month instead of the current week. No dedicated backend
 * endpoint — fetches `GET /entries` with a month-range date filter (via `usePeriodEntries`, shared
 * with Week) and aggregates client-side (`utils/aggregate.ts`, also shared with Week).
 */
export function MonthPage(): ReactElement {
  const [monthOffset, setMonthOffset] = useState(0);
  const [categories, setCategories] = useState<CategoryRead[]>([]);
  const [tags, setTags] = useState<TagRead[]>([]);

  const range = useMemo(() => getMonthRange(new Date(), monthOffset), [monthOffset]);
  const { entries, loading, error, reload } = usePeriodEntries(range.startDate, range.endDate);
  const { runningTimer, stop: stopRunningTimer } = useRunningTimer();

  useEffect(() => {
    listCategories()
      .then((response) => setCategories(response.items))
      .catch(() => undefined);
    listTags()
      .then((response) => setTags(response.items))
      .catch(() => undefined);
  }, []);

  // Month keyboard shortcuts, mirroring Week's (design/screens.md §2.4): ←/→ page months, T jumps
  // back to the current month.
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent): void {
      const target = event.target as HTMLElement | null;
      const isTextField = target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA");
      if (isTextField) return;
      if (event.key === "ArrowLeft") setMonthOffset((o) => o - 1);
      else if (event.key === "ArrowRight") setMonthOffset((o) => o + 1);
      else if (event.key === "t" || event.key === "T") setMonthOffset(0);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const days = useMemo(() => enumerateDays(range), [range]);
  const grouped = useMemo(() => groupByDay(entries), [entries]);
  const total = totalMinutes(entries);
  const categoryBreakdown = useMemo(() => breakdownByCategory(entries), [entries]);
  const tagBreakdown = useMemo(() => breakdownByTag(entries), [entries]);

  // Newest day first, mirroring Week's reverse-chronological entry ordering.
  const orderedDays = useMemo(() => [...days].reverse(), [days]);

  async function handleSaveEntry(entryId: number, values: EntryRowSaveValues): Promise<void> {
    await updateEntry(entryId, { title: values.title, category_id: values.category?.id ?? null });
    await reload();
  }

  async function handleDeleteEntry(entryId: number): Promise<void> {
    await deleteEntry(entryId);
    await reload();
  }

  return (
    <div className={styles.page}>
      {runningTimer && <TimerBanner runningTimer={runningTimer} onStop={() => void stopRunningTimer()} />}

      <header className={styles.header}>
        <h1 className={styles.title}>{formatMonthHeading(range)}</h1>
        <div className={styles.nav}>
          <button type="button" aria-label="Previous month" onClick={() => setMonthOffset((o) => o - 1)}>
            ‹
          </button>
          {monthOffset !== 0 && (
            <button type="button" className={styles.thisMonth} onClick={() => setMonthOffset(0)}>
              This month
            </button>
          )}
          <button type="button" aria-label="Next month" onClick={() => setMonthOffset((o) => o + 1)}>
            ›
          </button>
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
      ) : (
        <>
          <div className={styles.summaryGrid}>
            <div className={styles.summaryCard}>
              <p className={styles.totalLabel}>Total this month</p>
              <p className={styles.totalValue}>
                {total === 0 ? "0m — nothing logged yet this month" : formatDurationMinutes(total)}
              </p>
            </div>
            <div className={styles.breakdownCard}>
              <SegmentedBreakdown title="By category" segments={categoryBreakdown} variant="category" />
              <SegmentedBreakdown title="By tag" segments={tagBreakdown} variant="tag" visibleLimit={5} />
            </div>
          </div>

          <div className={styles.dayGroups}>
            {orderedDays.map((isoDate) => (
              <DayGroup
                key={isoDate}
                isoDate={isoDate}
                entries={(grouped.get(isoDate) ?? [])
                  .slice()
                  .sort((a, b) => b.start_ts.localeCompare(a.start_ts))}
                categories={categories}
                knownTags={tags}
                defaultExpanded={isToday(isoDate)}
                onSaveEntry={handleSaveEntry}
                onDeleteEntry={handleDeleteEntry}
                onAddEntry={async (entry) => {
                  await createEntry(entry);
                  await reload();
                }}
                onKnownTagsCreated={(created) => setTags((prev) => [...prev, ...created])}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
