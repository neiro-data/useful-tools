import { useCallback, useEffect, useState } from "react";
import { getCurrentTimer, stopTimer } from "../api/timer";
import type { EntryRead } from "../api/types";

interface UseRunningTimerResult {
  runningTimer: EntryRead | null;
  loading: boolean;
  refresh: () => Promise<void>;
  stop: () => Promise<void>;
}

/** Polls `GET /timer/current` so screens other than Today (Week, Month) can show the sticky
 * "timer running" banner without needing the full `/today` payload. Polls every 30s — a running
 * timer's live tick is rendered locally via `useLiveTimer`, this hook only needs to notice
 * start/stop transitions, not tick every second. */
export function useRunningTimer(pollMs = 30_000): UseRunningTimerResult {
  const [runningTimer, setRunningTimer] = useState<EntryRead | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    const response = await getCurrentTimer();
    setRunningTimer(response.entry);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    refresh()
      .catch(() => setRunningTimer(null))
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    const id = window.setInterval(() => {
      refresh().catch(() => undefined);
    }, pollMs);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [refresh, pollMs]);

  const stop = useCallback(async () => {
    await stopTimer();
    await refresh();
  }, [refresh]);

  return { runningTimer, loading, refresh, stop };
}
