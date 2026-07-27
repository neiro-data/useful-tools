import type { EntryRead, TagRead } from "../api/types";

/** Recently-used tags derived from an already-loaded list of entries, most-recent first — the
 * Week/Month screens' equivalent of `/today`'s `recent_tags` (which only covers today's entries).
 * Walks `entries` ordered by `start_ts` descending and collects each tag the first time it's seen,
 * capped at `limit`, so a tag used on several entries only contributes its most recent use to the
 * ordering. Pure/client-side: no extra API call, since Week/Month already hold their period's
 * entries in memory. */
export function recentTagsFromEntries(entries: EntryRead[], limit = 8): TagRead[] {
  const seen = new Set<number>();
  const recent: TagRead[] = [];

  const ordered = entries.slice().sort((a, b) => b.start_ts.localeCompare(a.start_ts));
  for (const entry of ordered) {
    for (const tag of entry.tags) {
      if (seen.has(tag.id)) continue;
      seen.add(tag.id);
      recent.push(tag);
      if (recent.length >= limit) return recent;
    }
  }

  return recent;
}
