import { useEffect, useMemo, useState, type ReactElement } from "react";
import { createEntry, deleteEntry, updateEntry } from "../../api/entries";
import { listCategories } from "../../api/categories";
import { listTags } from "../../api/tags";
import type { CategoryRead, TagRead } from "../../api/types";
import { usePeriodEntries } from "../../hooks/usePeriodEntries";
import { useRunningTimer } from "../../hooks/useRunningTimer";
import { DayGroup } from "../../components/DayGroup/DayGroup";
import { SegmentedBreakdown } from "../../components/SegmentedBreakdown/SegmentedBreakdown";
import { MiniBarChart } from "../../components/MiniBarChart/MiniBarChart";
import { barsFromDays } from "../../components/MiniBarChart/bars";
import { TimerBanner } from "../../components/TimerBanner/TimerBanner";
import { Skeleton } from "../../components/Skeleton/Skeleton";
import {
  getWeekRange,
  enumerateDays,
  formatCalendarWeek,
  formatWeekHeading,
  isToday,
} from "../../utils/dateRange";
import { breakdownByCategory, breakdownByTag, groupByDay, totalMinutes } from "../../utils/aggregate";
import { formatDurationMinutes } from "../../utils/duration";
import { resolveTagIds } from "../../utils/resolveTagIds";
import { recentTagsFromEntries } from "../../utils/recentTags";
import type { EntryRowSaveValues } from "../../components/EntryRow/EntryRow";
import styles from "./WeekPage.module.css";

export function WeekPage(): ReactElement {
  const [weekOffset, setWeekOffset] = useState(0);
  const [categories, setCategories] = useState<CategoryRead[]>([]);
  const [tags, setTags] = useState<TagRead[]>([]);

  const range = useMemo(() => getWeekRange(new Date(), weekOffset), [weekOffset]);
  const { entries, loading, error, reload } = usePeriodEntries(range.startDate, range.endDate);
  const { runningTimer, stop: stopRunningTimer } = useRunningTimer();

  useEffect(() => {
    listCategories()
      .then((response) => setCategories(response.items))
      .catch(() => undefined);
    listTags({ limit: 200 })
      .then((response) => setTags(response.items))
      .catch(() => undefined);
  }, []);

  // Week keyboard shortcuts (design/screens.md §2.4): ←/→ page weeks, T jumps to current week.
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent): void {
      const target = event.target as HTMLElement | null;
      const isTextField = target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA");
      if (isTextField) return;
      if (event.key === "ArrowLeft") setWeekOffset((o) => o - 1);
      else if (event.key === "ArrowRight") setWeekOffset((o) => o + 1);
      else if (event.key === "t" || event.key === "T") setWeekOffset(0);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const days = useMemo(() => enumerateDays(range), [range]);
  const grouped = useMemo(() => groupByDay(entries), [entries]);
  const total = totalMinutes(entries);
  const categoryBreakdown = useMemo(() => breakdownByCategory(entries), [entries]);
  const tagBreakdown = useMemo(() => breakdownByTag(entries), [entries]);
  const chartBars = barsFromDays(
    days.map((isoDate) => ({ isoDate, minutes: totalMinutes(grouped.get(isoDate) ?? []) })),
  );
  // Week has no `/today`-style server-supplied recent-tags list, so it's derived client-side from
  // the entries already loaded for this week (see `recentTagsFromEntries`'s doc comment).
  const recentTags = useMemo(() => recentTagsFromEntries(entries), [entries]);

  async function handleSaveEntry(entryId: number, values: EntryRowSaveValues): Promise<void> {
    const { ids, created } = await resolveTagIds(values.tagNames, tags);
    if (created.length > 0) setTags((prev) => [...prev, ...created]);
    await updateEntry(entryId, {
      title: values.title,
      category_id: values.category.id,
      tag_ids: ids,
      notes: values.notes,
      start_ts: values.startTs,
      // CRITICAL: only send end_ts when set — an explicit `end_ts: null` clears an
      // already-completed entry's end time (see `EntryRowSaveValues.endTs`'s doc comment).
      ...(values.endTs !== null && { end_ts: values.endTs }),
    });
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
        <h1 className={styles.title}>
          Week of {formatWeekHeading(range)}{" "}
          <span className={styles.calendarWeek}>({formatCalendarWeek(range.start)})</span>
        </h1>
        <div className={styles.nav}>
          <button type="button" aria-label="Previous week" onClick={() => setWeekOffset((o) => o - 1)}>
            ‹
          </button>
          {weekOffset !== 0 && (
            <button type="button" className={styles.thisWeek} onClick={() => setWeekOffset(0)}>
              This week
            </button>
          )}
          <button type="button" aria-label="Next week" onClick={() => setWeekOffset((o) => o + 1)}>
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
          <Skeleton height={180} />
          <Skeleton height={180} />
        </div>
      ) : (
        <>
          <div className={styles.summaryGrid}>
            <div className={styles.summaryCard}>
              <p className={styles.totalLabel}>Total this week</p>
              <p className={styles.totalValue}>
                {total === 0 ? "0m — nothing logged yet this week" : formatDurationMinutes(total)}
              </p>
              <MiniBarChart bars={chartBars} />
            </div>
            <div className={styles.breakdownCard}>
              <SegmentedBreakdown title="By category" segments={categoryBreakdown} variant="category" />
              <SegmentedBreakdown title="By tag" segments={tagBreakdown} variant="tag" visibleLimit={5} />
            </div>
          </div>

          <div className={styles.dayGroups}>
            {days.map((isoDate) => (
              <DayGroup
                key={isoDate}
                isoDate={isoDate}
                entries={(grouped.get(isoDate) ?? [])
                  .slice()
                  .sort((a, b) => b.start_ts.localeCompare(a.start_ts))}
                categories={categories}
                knownTags={tags}
                recentTags={recentTags}
                defaultExpanded={isToday(isoDate) || (grouped.get(isoDate)?.length ?? 0) > 0}
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
