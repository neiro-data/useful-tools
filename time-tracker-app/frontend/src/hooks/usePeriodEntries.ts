import { useCallback, useEffect, useRef, useState } from "react";
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
  const mountedRef = useRef(true);

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
    if (!mountedRef.current) return;
    setEntries(all);
  }, [startDate, endDate]);

  useEffect(() => {
    mountedRef.current = true;
    setLoading(true);
    reload()
      .catch((err) => {
        if (mountedRef.current) setError(err instanceof Error ? err.message : "Failed to load entries.");
      })
      .finally(() => {
        if (mountedRef.current) setLoading(false);
      });
    return () => {
      mountedRef.current = false;
    };
  }, [reload]);

  return { entries, loading, error, reload };
}
