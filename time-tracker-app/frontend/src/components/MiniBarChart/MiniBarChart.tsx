import type { ReactElement } from "react";
import { formatDurationMinutes } from "../../utils/duration";
import type { MiniBarChartBar } from "./bars";
import styles from "./MiniBarChart.module.css";

interface MiniBarChartProps {
  /** One entry per bucket (day or week), in chronological order. */
  bars: MiniBarChartBar[];
  /** Label every bar regardless of how many there are. Set this when the labels are short, fixed
   * width, and non-repeating (e.g. `barsFromWeeks`'s `"CW 27"`), where thinning would hide
   * information the labels could have carried. */
  labelEveryBar?: boolean;
}

/** Beyond a week, longer ranges (Month/Quarter) thin their labels to avoid crowding. */
const WEEK_LENGTH = 7;
/** Roughly this many labels are shown across a long range, regardless of its total length. */
const MAX_LONG_RANGE_LABELS = 8;

/** Mini bar chart for the Week/Month/Quarter summary card (`design/screens.md` §2.2): a neutral,
 * time-of-week shape — deliberately not colored by category so it doesn't compete with the
 * category legend. Ranges of 7 bars or fewer (a week of days) keep every label; longer ranges
 * (a month/quarter of days) thin the labels so they don't repeat/overlap, unless `labelEveryBar`
 * says the labels are narrow enough to all fit. Use `barsFromDays`/`barsFromWeeks` (from `./bars`)
 * to build `bars` from report API shapes. */
export function MiniBarChart({ bars, labelEveryBar = false }: MiniBarChartProps): ReactElement {
  const max = Math.max(1, ...bars.map((bar) => bar.minutes));
  const isLongRange = !labelEveryBar && bars.length > WEEK_LENGTH;
  const labelStep = isLongRange ? Math.max(1, Math.round(bars.length / MAX_LONG_RANGE_LABELS)) : 1;

  return (
    <div className={styles.chart}>
      {bars.map((bar, index) => {
        const showLabel = !isLongRange || index % labelStep === 0 || index === bars.length - 1;
        const tooltip = `${bar.title ?? bar.label}: ${formatDurationMinutes(bar.minutes)}`;
        return (
          <div key={bar.key} className={styles.column} title={tooltip}>
            <span className={styles.value}>{formatDurationMinutes(bar.minutes)}</span>
            <div className={styles.track}>
              <div
                className={bar.minutes === 0 ? styles.hairline : styles.bar}
                style={{ height: bar.minutes === 0 ? undefined : `${(bar.minutes / max) * 100}%` }}
              />
            </div>
            <span className={styles.label}>{showLabel ? bar.label : " "}</span>
          </div>
        );
      })}
    </div>
  );
}
