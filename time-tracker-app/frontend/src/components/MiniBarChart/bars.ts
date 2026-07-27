import { formatCalendarWeek, formatShortDate, formatWeekdayShort } from "../../utils/dateRange";

export interface MiniBarChartBar {
  key: string;
  label: string;
  minutes: number;
  /** Longer form of `label` for the bar's hover tooltip, when `label` is an abbreviation that
   * doesn't stand on its own (e.g. `"CW 27"` -> `"Jun 29 – Jul 5"`). */
  title?: string;
}

/** Beyond a week, repeating weekday names (Mon/Tue/…) become ambiguous, so longer ranges
 * (Month/Quarter) switch to date-based labels. Kept in sync with `MiniBarChart`'s own threshold. */
const WEEK_LENGTH = 7;

/** Builds chart bars from a chronological, zero-filled list of days. Week-length ranges label
 * every bar with the weekday (Mon/Tue/…); longer ranges switch to compact date labels. */
export function barsFromDays(days: { isoDate: string; minutes: number }[]): MiniBarChartBar[] {
  const isLongRange = days.length > WEEK_LENGTH;
  return days.map((day) => ({
    key: day.isoDate,
    label: isLongRange ? formatShortDate(day.isoDate) : formatWeekdayShort(day.isoDate),
    minutes: day.minutes,
  }));
}

/** Calendar-week label for a (possibly Sunday-start) bucket spanning `[weekStart, weekEnd]`.
 *
 * The backend's `week_start`/`week_end` follow `settings.week_starts_on`, which may be
 * Sunday-start, while ISO week numbers are always Monday-based. Deriving the number directly from
 * `week_start` is only correct for a Monday-start bucket: for a Sunday-start bucket, `week_start`
 * itself is a Sunday that — per the Monday-based ISO definition — belongs to the *previous* ISO
 * week, even though the other six days of this bucket (Mon–Sat) belong to the next one. Using
 * that Sunday would label the whole bucket off by one.
 *
 * The fix is to number the bucket by whichever of its days is a Thursday: ISO weeks are defined as
 * belonging to the year (and number) containing their Thursday, so scanning `[weekStart, weekEnd]`
 * for a Thursday and taking its ISO week number is correct regardless of which day the bucket
 * starts on. A heavily clipped edge bucket (a quarter's partial first/last week) may not contain a
 * Thursday at all, in which case this falls back to `weekStart` itself — clipping CAN move a
 * bucket's number by one in that narrow edge case, since there's no unambiguous "middle day" left
 * to anchor on. */
function calendarWeekLabelFor(weekStart: string, weekEnd: string): string {
  const start = new Date(`${weekStart}T00:00:00`);
  const end = new Date(`${weekEnd}T00:00:00`);
  let thursday = start;
  for (const cursor = new Date(start); cursor <= end; cursor.setDate(cursor.getDate() + 1)) {
    if (cursor.getDay() === 4) {
      thursday = cursor;
      break;
    }
  }
  return formatCalendarWeek(thursday);
}

/** Builds chart bars from `by_week` report rows, labeling each week by its calendar week (e.g.
 * `"CW 27"`).
 *
 * A `"Jun 29 – Jul 5"` date range is ~13 characters and can't fit under all ~13 bars of a quarter,
 * which is why those labels used to be thinned to every Nth bar — leaving most bars unlabeled. A
 * `"CW 27"` label always fits, so every bar can carry one. The full date range moves to each bar's
 * `title` tooltip (see `MiniBarChart`), so nothing is lost. See `calendarWeekLabelFor` for how the
 * week number itself is derived from the (possibly Sunday-start) `week_start`/`week_end` pair. */
export function barsFromWeeks(
  weeks: { week_start: string; week_end: string; total_minutes: number }[],
): MiniBarChartBar[] {
  return weeks.map((week) => ({
    key: week.week_start,
    label: calendarWeekLabelFor(week.week_start, week.week_end),
    title: formatWeekRangeShort(week.week_start, week.week_end),
    minutes: week.total_minutes,
  }));
}

export function formatWeekRangeShort(startDate: string, endDate: string): string {
  const start = new Date(`${startDate}T00:00:00`);
  const end = new Date(`${endDate}T00:00:00`);
  const startMonth = start.toLocaleDateString(undefined, { month: "short" });
  const endMonth = end.toLocaleDateString(undefined, { month: "short" });
  if (startMonth === endMonth) {
    return `${startMonth} ${start.getDate()}–${end.getDate()}`;
  }
  return `${startMonth} ${start.getDate()} – ${endMonth} ${end.getDate()}`;
}
