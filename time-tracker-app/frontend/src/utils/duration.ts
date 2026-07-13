/** Formats minutes as the design system's `H h MM m` display form (e.g. `1h 15m`, `45m`, `0m`). */
export function formatDurationMinutes(totalMinutes: number | null | undefined): string {
  if (totalMinutes === null || totalMinutes === undefined || Number.isNaN(totalMinutes)) return "0m";
  const minutes = Math.max(0, Math.round(totalMinutes));
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  if (hours === 0) return `${remainder}m`;
  return `${hours}h ${String(remainder).padStart(2, "0")}m`;
}

/** Formats an elapsed duration (in whole seconds) as `HH:MM:SS`, the live-timer-only display. */
export function formatElapsedSeconds(totalSeconds: number): string {
  const seconds = Math.max(0, Math.floor(totalSeconds));
  const hh = Math.floor(seconds / 3600);
  const mm = Math.floor((seconds % 3600) / 60);
  const ss = seconds % 60;
  const pad = (n: number): string => String(n).padStart(2, "0");
  return `${pad(hh)}:${pad(mm)}:${pad(ss)}`;
}

/** Seconds elapsed between an ISO-8601 start timestamp and now (or `until`, for testing). */
export function secondsSince(startIso: string, until: Date = new Date()): number {
  const start = new Date(startIso).getTime();
  return Math.max(0, Math.floor((until.getTime() - start) / 1000));
}

/** Minutes between two ISO timestamps (used for client-side aggregation on Week/Month). */
export function minutesBetween(startIso: string, endIso: string): number {
  const start = new Date(startIso).getTime();
  const end = new Date(endIso).getTime();
  return Math.max(0, (end - start) / 60_000);
}
