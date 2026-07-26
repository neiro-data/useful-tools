import { formatShortDate, formatWeekdayShort } from "../../utils/dateRange";

export interface MiniBarChartBar {
  key: string;
  label: string;
  minutes: number;
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

/** Builds chart bars from `by_week` report rows, labeling each week compactly (e.g. `"Jun 1–7"`,
 * or `"Jun 29 – Jul 5"` if the week spans months). */
export function barsFromWeeks(
  weeks: { week_start: string; week_end: string; total_minutes: number }[],
): MiniBarChartBar[] {
  return weeks.map((week) => ({
    key: week.week_start,
    label: formatWeekRangeShort(week.week_start, week.week_end),
    minutes: week.total_minutes,
  }));
}

function formatWeekRangeShort(startDate: string, endDate: string): string {
  const start = new Date(`${startDate}T00:00:00`);
  const end = new Date(`${endDate}T00:00:00`);
  const startMonth = start.toLocaleDateString(undefined, { month: "short" });
  const endMonth = end.toLocaleDateString(undefined, { month: "short" });
  if (startMonth === endMonth) {
    return `${startMonth} ${start.getDate()}–${end.getDate()}`;
  }
  return `${startMonth} ${start.getDate()} – ${endMonth} ${end.getDate()}`;
}
