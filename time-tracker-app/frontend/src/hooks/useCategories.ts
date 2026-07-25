import { useCallback, useEffect, useRef, useState } from "react";
import { listCategories } from "../api/categories";
import type { CategoryRead } from "../api/types";

/** Fetches `GET /categories` (active only). Mirrors `useReportSummary`'s cancelled-guard +
 * loading/error handling. Exposes `reload` so callers can refresh the list after creating a
 * category rather than duplicating fetch logic. */
export function useCategories(): {
  categories: CategoryRead[];
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
} {
  const [categories, setCategories] = useState<CategoryRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const reload = useCallback(async () => {
    setError(null);
    const response = await listCategories();
    if (!mountedRef.current) return;
    setCategories(response.items);
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    setLoading(true);
    reload()
      .catch((err) => {
        if (mountedRef.current) {
          setError(err instanceof Error ? err.message : "Failed to load categories.");
        }
      })
      .finally(() => {
        if (mountedRef.current) setLoading(false);
      });
    return () => {
      mountedRef.current = false;
    };
  }, [reload]);

  return { categories, loading, error, reload };
}
