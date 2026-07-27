/**
 * Shared start/end validation for every form that edits an entry's time range (`TimerWidget`'s
 * manual mode, `ManualEntryForm`, `EntryRow`'s inline edit).
 *
 * The backend already rejects `end_ts < start_ts` (`EntryCreateManual` / `EntryUpdate` in
 * `app/schemas.py`, plus the effective-pair check in `app/routers/entries.py`), so this is not the
 * enforcement boundary — it exists so the UI can block the action and say why *before* a doomed
 * request, rather than surfacing a 422 after the fact. Keep the rule identical to the backend's:
 * `end == start` is allowed (a zero-length entry), only `end < start` is rejected.
 */

/** Returns a user-facing message when the range is invalid, or `null` when it's fine.
 *
 * Accepts the `YYYY-MM-DDTHH:mm` local strings the `DateTimePicker` emits. An unparseable value
 * yields its own message rather than `null`: `new Date("…")` on garbage gives `NaN`, and every
 * comparison against `NaN` is false, so treating it as valid would let a silently-broken timestamp
 * through to `toISOString()` (which throws).
 */
/** Formats an instant as the local `YYYY-MM-DDTHH:mm` string `DateTimePicker` expects.
 *
 * Note this is NOT `date.toISOString().slice(0, 16)`: `toISOString` renders UTC, so feeding its
 * output to a picker that reads its value as local time silently shifts every prefilled time by the
 * viewer's UTC offset (an hour or two off in Europe, a day off near midnight). Accepts an ISO
 * string (e.g. an entry's `start_ts`) or a `Date`.
 */
export function toLocalDateTimeInput(instant: string | Date): string {
  const date = typeof instant === "string" ? new Date(instant) : instant;
  const pad = (value: number): string => String(value).padStart(2, "0");
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}`
  );
}

export function timeRangeError(start: string, end: string): string | null {
  const startMs = new Date(start).getTime();
  const endMs = new Date(end).getTime();
  if (Number.isNaN(startMs) || Number.isNaN(endMs)) {
    return "Start and end must both be valid dates and times.";
  }
  if (endMs < startMs) {
    return "End must be on or after start.";
  }
  return null;
}
