/**
 * Pure date-range helpers for the Week/Month screens. Deliberately dependency-free (per
 * `design/screens.md`'s "the design doesn't assume a specific date library" note) — all
 * arithmetic is done on local-time `Date` instances since these screens group/label by the
 * viewer's local calendar day.
 */

export interface DateRange {
  /** Inclusive, `YYYY-MM-DD`. */
  startDate: string;
  /** Inclusive, `YYYY-MM-DD`. */
  endDate: string;
  start: Date;
  end: Date;
}

function toIsoDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function startOfDay(date: Date): Date {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  return d;
}

/** Monday-start week containing `reference`, offset by `weekOffset` whole weeks. */
export function getWeekRange(reference: Date, weekOffset = 0): DateRange {
  const day = reference.getDay(); // 0 = Sunday
  const mondayOffset = day === 0 ? -6 : 1 - day;
  const start = startOfDay(reference);
  start.setDate(start.getDate() + mondayOffset + weekOffset * 7);
  const end = new Date(start);
  end.setDate(end.getDate() + 6);
  return { startDate: toIsoDate(start), endDate: toIsoDate(end), start, end };
}

/** Calendar month containing `reference`, offset by `monthOffset` whole months. */
export function getMonthRange(reference: Date, monthOffset = 0): DateRange {
  const start = new Date(reference.getFullYear(), reference.getMonth() + monthOffset, 1);
  const end = new Date(reference.getFullYear(), reference.getMonth() + monthOffset + 1, 0);
  return { startDate: toIsoDate(start), endDate: toIsoDate(end), start, end };
}

/** All calendar days in `range`, inclusive, as `YYYY-MM-DD` strings. */
export function enumerateDays(range: DateRange): string[] {
  const days: string[] = [];
  const cursor = new Date(range.start);
  while (cursor <= range.end) {
    days.push(toIsoDate(cursor));
    cursor.setDate(cursor.getDate() + 1);
  }
  return days;
}

/** The local `YYYY-MM-DD` bucket an ISO timestamp falls into (for day-grouping). */
export function isoDateOf(timestamp: string): string {
  return toIsoDate(new Date(timestamp));
}

const WEEKDAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const WEEKDAY_SHORT = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

/** e.g. `"Monday, Jul 7"`. */
export function formatDayHeading(isoDate: string): string {
  const date = new Date(`${isoDate}T00:00:00`);
  const weekday = WEEKDAY_NAMES[date.getDay()] ?? "";
  const month = date.toLocaleDateString(undefined, { month: "short" });
  return `${weekday}, ${month} ${date.getDate()}`;
}

/** e.g. `"Mon"` for the mini bar chart's per-day label. */
export function formatWeekdayShort(isoDate: string): string {
  const date = new Date(`${isoDate}T00:00:00`);
  return WEEKDAY_SHORT[date.getDay()] ?? "";
}

/** e.g. `"Jul 7"` — a compact date label used when a range is too long for repeating weekday
 * names to stay unambiguous (e.g. `MiniBarChart` over a month/quarter). */
export function formatShortDate(isoDate: string): string {
  const date = new Date(`${isoDate}T00:00:00`);
  const month = date.toLocaleDateString(undefined, { month: "short" });
  return `${month} ${date.getDate()}`;
}

/** e.g. `"Jul 7 – 13"` for the Week header, or `"Jul 7 – Aug 2"` if the range spans months. */
export function formatWeekHeading(range: DateRange): string {
  const startMonth = range.start.toLocaleDateString(undefined, { month: "short" });
  const endMonth = range.end.toLocaleDateString(undefined, { month: "short" });
  if (startMonth === endMonth) {
    return `${startMonth} ${range.start.getDate()}–${range.end.getDate()}`;
  }
  return `${startMonth} ${range.start.getDate()} – ${endMonth} ${range.end.getDate()}`;
}

/** e.g. `"July 2026"` for the Month header. */
export function formatMonthHeading(range: DateRange): string {
  return range.start.toLocaleDateString(undefined, { month: "long", year: "numeric" });
}

/** True when `isoDate` is today's local date. */
export function isToday(isoDate: string): boolean {
  return isoDate === toIsoDate(new Date());
}
