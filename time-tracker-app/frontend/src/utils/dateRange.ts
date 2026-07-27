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

/** ISO-8601 week number (1–53) of the week containing `date`.
 *
 * ISO weeks are Monday-start and belong to the year containing their Thursday, so the number is
 * derived from that Thursday rather than from `date` itself — this is what makes Dec 29–31 land in
 * week 1 of the next year (and Jan 1–3 in week 52/53 of the previous one) instead of overflowing to
 * 53/54. Arithmetic stays on local midnights; the `Math.round` absorbs the ±1h a DST transition
 * introduces between the two Thursdays. */
export function isoWeekNumber(date: Date): number {
  const thursday = thursdayOfIsoWeek(new Date(date.getFullYear(), date.getMonth(), date.getDate()));
  // Jan 4 is always in ISO week 1, so its week's Thursday anchors week 1 of that ISO year.
  const firstThursday = thursdayOfIsoWeek(new Date(thursday.getFullYear(), 0, 4));
  const DAY_MS = 86_400_000;
  return 1 + Math.round((thursday.getTime() - firstThursday.getTime()) / (7 * DAY_MS));
}

function thursdayOfIsoWeek(date: Date): Date {
  const mondayIndex = (date.getDay() + 6) % 7; // 0 = Monday … 6 = Sunday
  const thursday = new Date(date);
  thursday.setDate(thursday.getDate() + 3 - mondayIndex);
  return thursday;
}

/** e.g. `"CW 07"` / `"CW 29"` — the zero-padded calendar-week label used in the Week header and as
 * the Quarter report's per-bar x-label. */
export function formatCalendarWeek(date: Date): string {
  return `CW ${String(isoWeekNumber(date)).padStart(2, "0")}`;
}

/** `formatCalendarWeek` for a `YYYY-MM-DD` string (e.g. a report's `week_start`). */
export function formatCalendarWeekOfIsoDate(isoDate: string): string {
  return formatCalendarWeek(new Date(`${isoDate}T00:00:00`));
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
