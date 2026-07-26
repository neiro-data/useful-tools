import type { EntryRead } from "../api/types";
import { isoDateOf } from "./dateRange";

export interface BreakdownSegment {
  key: string;
  label: string;
  /** Category color token key (e.g. `"blue"`), or `null` for the monochrome tag breakdown. */
  colorKey: string | null;
  minutes: number;
  percent: number;
}

/** Only entries with a resolved (non-null) `duration_minutes` count toward totals/breakdowns —
 * i.e. finished entries. The live running timer is tracked separately by the caller. */
function finishedMinutes(entry: EntryRead): number {
  return entry.duration_minutes ?? 0;
}

export function totalMinutes(entries: EntryRead[]): number {
  return entries.reduce((sum, entry) => sum + finishedMinutes(entry), 0);
}

/** Groups entries by local calendar day (`YYYY-MM-DD`), most granular unit Week/Month need. */
export function groupByDay(entries: EntryRead[]): Map<string, EntryRead[]> {
  const groups = new Map<string, EntryRead[]>();
  for (const entry of entries) {
    const day = isoDateOf(entry.start_ts);
    const bucket = groups.get(day);
    if (bucket) bucket.push(entry);
    else groups.set(day, [entry]);
  }
  return groups;
}

export function breakdownByCategory(entries: EntryRead[]): BreakdownSegment[] {
  const totals = new Map<string, { label: string; colorKey: string | null; minutes: number }>();
  for (const entry of entries) {
    const key = `cat-${entry.category.id}`;
    const label = entry.category.name;
    const colorKey = entry.category.color ?? "slate";
    const existing = totals.get(key);
    const minutes = finishedMinutes(entry);
    if (existing) existing.minutes += minutes;
    else totals.set(key, { label, colorKey, minutes });
  }
  const grandTotal = [...totals.values()].reduce((sum, t) => sum + t.minutes, 0);
  return [...totals.entries()]
    .map(([key, value]) => ({
      key,
      label: value.label,
      colorKey: value.colorKey,
      minutes: value.minutes,
      percent: grandTotal > 0 ? (value.minutes / grandTotal) * 100 : 0,
    }))
    .sort((a, b) => b.minutes - a.minutes);
}

/** One Monday-start week bucket for `MonthPage`'s mini bar chart. `weekStart`/`weekEnd` are
 * `YYYY-MM-DD`, clipped to `[rangeStart, rangeEnd]` (a calendar month rarely starts/ends on a
 * Monday), so the buckets always sum to the month's total. */
export interface WeekBucket {
  weekStart: string;
  weekEnd: string;
  minutes: number;
}

function toIsoDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

/** Buckets `entries` into Monday-start weeks spanning `[rangeStart, rangeEnd]` (inclusive,
 * `YYYY-MM-DD`), clipping the first/last bucket to the range bounds. Used by `MonthPage`, which
 * aggregates client-side from `/entries` rather than a report endpoint. */
export function groupByWeek(entries: EntryRead[], rangeStart: string, rangeEnd: string): WeekBucket[] {
  const grouped = groupByDay(entries);
  const rangeStartDate = new Date(`${rangeStart}T00:00:00`);
  const rangeEndDate = new Date(`${rangeEnd}T00:00:00`);

  const firstDay = rangeStartDate.getDay(); // 0 = Sunday
  const mondayOffset = firstDay === 0 ? -6 : 1 - firstDay;
  const cursor = new Date(rangeStartDate);
  cursor.setDate(cursor.getDate() + mondayOffset);

  const buckets: WeekBucket[] = [];
  while (cursor <= rangeEndDate) {
    const weekMonday = new Date(cursor);
    const weekSunday = new Date(cursor);
    weekSunday.setDate(weekSunday.getDate() + 6);

    const clippedStart = weekMonday < rangeStartDate ? rangeStartDate : weekMonday;
    const clippedEnd = weekSunday > rangeEndDate ? rangeEndDate : weekSunday;

    let minutes = 0;
    const day = new Date(clippedStart);
    while (day <= clippedEnd) {
      minutes += totalMinutes(grouped.get(toIsoDate(day)) ?? []);
      day.setDate(day.getDate() + 1);
    }

    buckets.push({ weekStart: toIsoDate(clippedStart), weekEnd: toIsoDate(clippedEnd), minutes });
    cursor.setDate(cursor.getDate() + 7);
  }

  return buckets;
}

export function breakdownByTag(entries: EntryRead[]): BreakdownSegment[] {
  const totals = new Map<string, { label: string; minutes: number }>();
  for (const entry of entries) {
    const minutes = finishedMinutes(entry);
    if (entry.tags.length === 0) {
      const existing = totals.get("untagged");
      if (existing) existing.minutes += minutes;
      else totals.set("untagged", { label: "Untagged", minutes });
      continue;
    }
    for (const tag of entry.tags) {
      const key = `tag-${tag.id}`;
      const existing = totals.get(key);
      if (existing) existing.minutes += minutes;
      else totals.set(key, { label: `#${tag.name}`, minutes });
    }
  }
  const grandTotal = [...totals.values()].reduce((sum, t) => sum + t.minutes, 0);
  return [...totals.entries()]
    .map(([key, value]) => ({
      key,
      label: value.label,
      colorKey: null,
      minutes: value.minutes,
      percent: grandTotal > 0 ? (value.minutes / grandTotal) * 100 : 0,
    }))
    .sort((a, b) => b.minutes - a.minutes);
}
