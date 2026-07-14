import type { ReactElement } from "react";
import { formatDurationMinutes } from "../../utils/duration";
import { formatShortDate, formatWeekdayShort } from "../../utils/dateRange";
import styles from "./MiniBarChart.module.css";

interface MiniBarChartProps {
  /** One entry per day, in chronological order. */
  days: { isoDate: string; minutes: number }[];
}

/** Beyond a week, repeating weekday names (Mon/Tue/…) become ambiguous, so longer ranges
 * (Month/Quarter) switch to date-based labels and thin them to avoid crowding. */
const WEEK_LENGTH = 7;
/** Roughly this many labels are shown across a long range, regardless of its total length. */
const MAX_LONG_RANGE_LABELS = 8;

/** Mini bar chart for the Week/Month/Quarter summary card (`design/screens.md` §2.2): a neutral,
 * time-of-week shape — deliberately not colored by category so it doesn't compete with the
 * category legend. Week-length ranges keep the original Mon/Tue/… labels; longer ranges label by
 * date and thin the labels so they don't repeat/overlap. */
export function MiniBarChart({ days }: MiniBarChartProps): ReactElement {
  const max = Math.max(1, ...days.map((day) => day.minutes));
  const isLongRange = days.length > WEEK_LENGTH;
  const labelStep = isLongRange ? Math.max(1, Math.round(days.length / MAX_LONG_RANGE_LABELS)) : 1;

  return (
    <div className={styles.chart}>
      {days.map((day, index) => {
        const showLabel = !isLongRange || index % labelStep === 0 || index === days.length - 1;
        const label = isLongRange ? formatShortDate(day.isoDate) : formatWeekdayShort(day.isoDate);
        return (
          <div key={day.isoDate} className={styles.column}>
            <span className={styles.value}>{formatDurationMinutes(day.minutes)}</span>
            <div className={styles.track}>
              <div
                className={day.minutes === 0 ? styles.hairline : styles.bar}
                style={{ height: day.minutes === 0 ? undefined : `${(day.minutes / max) * 100}%` }}
              />
            </div>
            <span className={styles.label}>{showLabel ? label : " "}</span>
          </div>
        );
      })}
    </div>
  );
}
