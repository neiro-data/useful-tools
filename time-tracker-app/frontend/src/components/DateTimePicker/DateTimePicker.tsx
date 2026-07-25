import type { ReactElement } from "react";
import styles from "./DateTimePicker.module.css";

interface DateTimePickerProps {
  /** `YYYY-MM-DDTHH:mm`, matching the wire format everywhere else in the app. */
  value: string;
  onChange: (value: string) => void;
  /** Label prefix used to build each control's accessible name, e.g. "Start" ->
   * "Start date" / "Start hour" / "Start minute". */
  label: string;
}

const HOURS = Array.from({ length: 24 }, (_, hour) => hour.toString().padStart(2, "0"));
const MINUTES = Array.from({ length: 60 }, (_, minute) => minute.toString().padStart(2, "0"));

interface ParsedValue {
  date: string;
  hour: string;
  minute: string;
}

/** Splits a `YYYY-MM-DDTHH:mm` string into its date/hour/minute parts, tolerating a malformed or
 * empty `value` (falls back to today's date at midnight rather than throwing). */
function parseValue(value: string): ParsedValue {
  const [datePart, timePart] = value.split("T");
  const validDate = datePart && /^\d{4}-\d{2}-\d{2}$/.test(datePart) ? datePart : todayIso();
  const [hourPart, minutePart] = (timePart ?? "").split(":");
  const validHour = hourPart && isInRange(hourPart, 0, 23) ? hourPart : "00";
  const validMinute = minutePart && isInRange(minutePart, 0, 59) ? minutePart : "00";
  return { date: validDate, hour: validHour, minute: validMinute };
}

/** Matches a 2-digit numeric string whose value falls within `[min, max]`, rejecting anything
 * out of range (e.g. "61" for minutes, "24" for hours) instead of injecting it as-is. */
function isInRange(part: string, min: number, max: number): boolean {
  if (!/^\d{2}$/.test(part)) return false;
  const value = Number(part);
  return value >= min && value <= max;
}

function todayIso(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = (now.getMonth() + 1).toString().padStart(2, "0");
  const day = now.getDate().toString().padStart(2, "0");
  return `${year}-${month}-${day}`;
}

/** Shared 24-hour date/hour/minute picker used by `TimerWidget`'s manual mode and
 * `ManualEntryForm`, replacing the native `datetime-local` input (whose browser-rendered popover
 * intercepted 1-6 keystrokes and offered no minute granularity control). Minutes are offered at
 * 1-minute granularity (00-59), so any valid value is directly selectable. Emits/accepts the same
 * `YYYY-MM-DDTHH:mm` string so callers doing `new Date(value).toISOString()` are unaffected. */
export function DateTimePicker({ value, onChange, label }: DateTimePickerProps): ReactElement {
  const { date, hour, minute } = parseValue(value);

  function emit(nextDate: string, nextHour: string, nextMinute: string): void {
    onChange(`${nextDate}T${nextHour}:${nextMinute}`);
  }

  return (
    <div className={styles.picker}>
      <input
        type="date"
        className={styles.dateInput}
        value={date}
        onChange={(event) => emit(event.target.value, hour, minute)}
        aria-label={`${label} date`}
      />
      <select
        className={styles.select}
        value={hour}
        onChange={(event) => emit(date, event.target.value, minute)}
        aria-label={`${label} hour`}
      >
        {HOURS.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
      <span className={styles.separator} aria-hidden="true">
        :
      </span>
      <select
        className={styles.select}
        value={minute}
        onChange={(event) => emit(date, hour, event.target.value)}
        aria-label={`${label} minute`}
      >
        {MINUTES.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </div>
  );
}
