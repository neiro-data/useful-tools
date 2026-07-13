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
    const key = entry.category ? `cat-${entry.category.id}` : "uncategorized";
    const label = entry.category ? entry.category.name : "Uncategorized";
    const colorKey = entry.category?.color ?? "slate";
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
