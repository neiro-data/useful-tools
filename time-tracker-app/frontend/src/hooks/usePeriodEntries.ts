import { useCallback, useEffect, useState } from "react";
import { listEntries } from "../api/entries";
import type { EntryRead } from "../api/types";

const PAGE_SIZE = 200;

/** Fetches *all* entries in `[startDate, endDate]` (inclusive), paging through `GET /entries` as
 * needed — Week/Month aggregate client-side over the full range, so partial pages would silently
 * under-count totals. */
export function usePeriodEntries(
  startDate: string,
  endDate: string,
): {
  entries: EntryRead[];
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
} {
  const [entries, setEntries] = useState<EntryRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setError(null);
    const all: EntryRead[] = [];
    let offset = 0;
    for (;;) {
      const page = await listEntries({ start_date: startDate, end_date: endDate, limit: PAGE_SIZE, offset });
      all.push(...page.items);
      offset += PAGE_SIZE;
      if (offset >= page.total) break;
    }
    setEntries(all);
  }, [startDate, endDate]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    reload()
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load entries.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [reload]);

  return { entries, loading, error, reload };
}
