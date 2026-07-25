import { useCallback, useEffect, useRef, useState } from "react";
import { listTimezones } from "../api/settings";
import type { TimezoneOption } from "../api/types";

/** Fetches `GET /settings/timezones` for the Settings timezone dropdown. Mirrors
 * `useReportSummary`'s cancelled-guard + loading/error handling. The list is optional UX sugar —
 * callers should degrade gracefully (e.g. fall back to the currently saved zone) when `error` is
 * set, rather than blocking the rest of the Settings form. */
export function useTimezones(): {
  timezones: TimezoneOption[];
  loading: boolean;
  error: string | null;
} {
  const [timezones, setTimezones] = useState<TimezoneOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const reload = useCallback(async () => {
    setError(null);
    const response = await listTimezones();
    if (!mountedRef.current) return;
    setTimezones(response.items);
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    setLoading(true);
    reload()
      .catch((err) => {
        if (mountedRef.current) {
          setError(err instanceof Error ? err.message : "Failed to load timezones.");
        }
      })
      .finally(() => {
        if (mountedRef.current) setLoading(false);
      });
    return () => {
      mountedRef.current = false;
    };
  }, [reload]);

  return { timezones, loading, error };
}
