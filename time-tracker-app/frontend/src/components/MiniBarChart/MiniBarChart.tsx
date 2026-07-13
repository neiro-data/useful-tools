import type { ReactElement } from "react";
import { formatDurationMinutes } from "../../utils/duration";
import { formatWeekdayShort } from "../../utils/dateRange";
import styles from "./MiniBarChart.module.css";

interface MiniBarChartProps {
  /** One entry per day, in chronological order. */
  days: { isoDate: string; minutes: number }[];
}

/** 7-day mini bar chart for the Week summary card (`design/screens.md` §2.2): a neutral,
 * time-of-week shape — deliberately not colored by category so it doesn't compete with the
 * category legend. */
export function MiniBarChart({ days }: MiniBarChartProps): ReactElement {
  const max = Math.max(1, ...days.map((day) => day.minutes));
  return (
    <div className={styles.chart}>
      {days.map((day) => (
        <div key={day.isoDate} className={styles.column}>
          <span className={styles.value}>{formatDurationMinutes(day.minutes)}</span>
          <div className={styles.track}>
            <div
              className={day.minutes === 0 ? styles.hairline : styles.bar}
              style={{ height: day.minutes === 0 ? undefined : `${(day.minutes / max) * 100}%` }}
            />
          </div>
          <span className={styles.label}>{formatWeekdayShort(day.isoDate)}</span>
        </div>
      ))}
    </div>
  );
}
