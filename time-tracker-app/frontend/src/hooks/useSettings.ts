import { useCallback, useEffect, useState } from "react";
import { getSettings, updateSettings } from "../api/settings";
import type { SettingsRead, SettingsUpdate } from "../api/types";

/** Fetches `GET /settings` and exposes a `save` helper backed by `PATCH /settings`. Mirrors
 * `useReportSummary`'s cancelled-guard + loading/error handling. Backend error messages (including
 * timezone validation) are surfaced as-is via `ApiError.message` — no client-side duplication. */
export function useSettings(): {
  settings: SettingsRead | null;
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
  save: (update: SettingsUpdate) => Promise<void>;
} {
  const [settings, setSettings] = useState<SettingsRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setError(null);
    const response = await getSettings();
    setSettings(response);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    reload()
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load settings.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [reload]);

  const save = useCallback(async (update: SettingsUpdate) => {
    const response = await updateSettings(update);
    setSettings(response);
  }, []);

  return { settings, loading, error, reload, save };
}
