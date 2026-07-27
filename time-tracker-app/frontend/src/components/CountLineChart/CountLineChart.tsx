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

/** The polyline's coordinate space and each marker's `left`/`top` percentage share this same
 * 0–100 scale, so a point computed once can drive both the SVG line and the HTML marker without
 * a second unit conversion. */
const PLOT_SIZE = 100;
/** Reserved at the top of the plot for the per-point count label, so the tallest point's label
 * isn't clipped by the plot box edge. Percentage of `PLOT_SIZE`, matching the y-axis scale. */
const TOP_HEADROOM = 22;
/** Small bottom margin so a marker at count 0 doesn't sit flush against the plot's bottom edge. */
const BOTTOM_MARGIN = 6;
const USABLE_HEIGHT = PLOT_SIZE - TOP_HEADROOM - BOTTOM_MARGIN;

/** Number-of-entries-per-bucket chart for the Reports screen: a single polyline + one labeled,
 * round marker per bucket, sharing the same bucket list/order as `StackedCategoryChart` so the
 * two charts stay in lockstep. No charting library.
 *
 * Markers are rendered as absolutely-positioned HTML elements rather than SVG `<circle>`s inside
 * the `preserveAspectRatio="none"` viewBox: that non-uniform scaling (needed to let the polyline
 * fill a wide-and-short container) stretches circles into ellipses. Splitting the two — an SVG
 * only for the polyline, HTML markers layered on top of it via a shared `position: relative` plot
 * box — keeps the line filling its box while the markers stay perfectly round.
 *
 * Each point's x sits at `(index + 0.5) / points.length` of the plot width — the centre of the
 * point's "slot" — rather than spreading points edge-to-edge across `[0, 1]`. That's what lines
 * point i up with `StackedCategoryChart`'s column i (see that component's `.columns`, which drops
 * its `gap` for the same reason): both charts divide the width into `N` equal slots and centre
 * their per-bucket visual in slot i.
 */
export function CountLineChart({ points }: CountLineChartProps): ReactElement {
  if (points.length === 0) {
    return <div className={styles.chart} />;
  }

  const max = Math.max(1, ...points.map((point) => point.count));

  const coords = points.map((point, index) => {
    const x = ((index + 0.5) / points.length) * PLOT_SIZE;
    const y = TOP_HEADROOM + USABLE_HEIGHT * (1 - point.count / max);
    return { ...point, x, y };
  });

  return (
    <div className={styles.chart}>
      {/* `role="img"`/`aria-label` describes the chart as a whole on this wrapper (it now mixes
          an SVG line with HTML marker/label elements, so no single element can carry that
          semantic alone). The SVG and the per-point count labels are supplemental/visual, so
          they're `aria-hidden` to avoid a screen reader re-announcing the same information
          point-by-point right after this summary. */}
      <div className={styles.plot} role="img" aria-label="Number of entries per bucket">
        <svg
          className={styles.svg}
          viewBox={`0 0 ${PLOT_SIZE} ${PLOT_SIZE}`}
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          {coords.length > 1 && (
            <polyline
              className={styles.line}
              vectorEffect="non-scaling-stroke"
              points={coords.map((point) => `${point.x},${point.y}`).join(" ")}
            />
          )}
        </svg>
        {coords.map((point) => {
          const tooltip = `${point.title ?? point.label}: ${point.count} ${point.count === 1 ? "entry" : "entries"}`;
          return (
            <div key={point.key} className={styles.point} style={{ left: `${point.x}%`, top: `${point.y}%` }}>
              <span className={styles.countLabel} aria-hidden="true">
                {point.count}
              </span>
              <span className={styles.marker} title={tooltip} />
            </div>
          );
        })}
      </div>
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
