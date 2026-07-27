import type { ReactElement } from "react";
import styles from "./CountLineChart.module.css";

export interface CountLineChartPoint {
  key: string;
  label: string;
  /** Longer form of `label` for the point's hover tooltip, matching `MiniBarChart`'s convention. */
  title?: string;
  count: number;
}

interface CountLineChartProps {
  /** One point per bucket (day or week), in chronological order. */
  points: CountLineChartPoint[];
}

const VIEW_WIDTH = 300;
const VIEW_HEIGHT = 100;
/** Keeps circle markers (radius included) from clipping against the viewBox edges. */
const PADDING = 8;

/** Number-of-entries-per-bucket chart for the Reports screen: a single polyline + one labeled
 * marker per bucket, sharing the same bucket list/order as `StackedCategoryChart` so the two
 * charts stay in lockstep. Hand-rolled inline SVG (no charting library), `preserveAspectRatio`d
 * to fill its container; `vector-effect="non-scaling-stroke"` keeps the line/marker stroke a
 * constant on-screen width regardless of that scaling. */
export function CountLineChart({ points }: CountLineChartProps): ReactElement {
  if (points.length === 0) {
    return <div className={styles.chart} />;
  }

  const max = Math.max(1, ...points.map((point) => point.count));
  const usableWidth = VIEW_WIDTH - PADDING * 2;
  const usableHeight = VIEW_HEIGHT - PADDING * 2;

  const coords = points.map((point, index) => {
    const x =
      points.length === 1 ? VIEW_WIDTH / 2 : PADDING + (index / (points.length - 1)) * usableWidth;
    const y = PADDING + usableHeight * (1 - point.count / max);
    return { ...point, x, y };
  });

  return (
    <div className={styles.chart}>
      <svg
        className={styles.svg}
        viewBox={`0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}`}
        preserveAspectRatio="none"
        role="img"
        aria-label="Number of entries per bucket"
      >
        {coords.length > 1 && (
          <polyline
            className={styles.line}
            vectorEffect="non-scaling-stroke"
            points={coords.map((point) => `${point.x},${point.y}`).join(" ")}
          />
        )}
        {coords.map((point) => (
          <circle
            key={point.key}
            className={styles.marker}
            cx={point.x}
            cy={point.y}
            r={4}
            vectorEffect="non-scaling-stroke"
          >
            <title>{`${point.title ?? point.label}: ${point.count} ${point.count === 1 ? "entry" : "entries"}`}</title>
          </circle>
        ))}
      </svg>
      <div className={styles.labels}>
        {points.map((point) => (
          <span key={point.key} className={styles.label}>
            {point.label}
          </span>
        ))}
      </div>
    </div>
  );
}
