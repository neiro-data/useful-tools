import type { ReactElement } from "react";
import { categoryColorVar } from "../../utils/categoryColor";
import { formatDurationMinutes } from "../../utils/duration";
import styles from "./StackedCategoryChart.module.css";

export interface StackedCategoryLegendItem {
  /** `null` groups uncategorized time, mirroring `ReportBucketCategorySplit.category_id`. */
  categoryId: number | null;
  name: string;
  /** The category's stored color token (palette key or hex) — `null`/uncategorized resolves to
   * `slate` via `categoryColorVar`. */
  color: string | null;
}

export interface StackedCategoryBucket {
  key: string;
  label: string;
  /** Longer form of `label` for the column's hover tooltip, matching `MiniBarChart`'s convention. */
  title?: string;
  segments: { categoryId: number | null; minutes: number }[];
}

interface StackedCategoryChartProps {
  /** One entry per bucket (day or week), in chronological order. */
  buckets: StackedCategoryBucket[];
  /** Ordered desc by total minutes (i.e. the report's top-level `by_category` order) — this both
   * drives the legend's order and each column's stacking order. */
  legend: StackedCategoryLegendItem[];
}

/** Hours-by-category chart for the Reports screen: a per-bucket (day/week) vertical stack of
 * category segments, each segment's height proportional to that category's share of the bucket,
 * and each column's total height proportional to the period's busiest bucket — mirroring
 * `MiniBarChart`'s neutral bar sizing, but colored per category. No charting library: hand-rolled
 * flex columns, consistent with the rest of the report charts (see `CountLineChart` for the SVG
 * counterpart). */
export function StackedCategoryChart({ buckets, legend }: StackedCategoryChartProps): ReactElement {
  const colorById = new Map(legend.map((item) => [item.categoryId, item.color]));
  const nameById = new Map(legend.map((item) => [item.categoryId, item.name]));
  const order = new Map(legend.map((item, index) => [item.categoryId, index]));

  const bucketTotals = buckets.map((bucket) =>
    bucket.segments.reduce((sum, segment) => sum + segment.minutes, 0),
  );
  const max = Math.max(1, ...bucketTotals);

  return (
    <div className={styles.chart}>
      {legend.length > 0 && (
        <ul className={styles.legend}>
          {legend.map((item) => (
            <li key={item.categoryId ?? "uncategorized"} className={styles.legendItem}>
              <span
                className={styles.swatch}
                style={{ background: categoryColorVar(item.color) }}
                aria-hidden="true"
              />
              {item.name}
            </li>
          ))}
        </ul>
      )}
      <div className={styles.columns}>
        {buckets.map((bucket, index) => {
          const total = bucketTotals[index] ?? 0;
          const orderedSegments = bucket.segments
            .filter((segment) => segment.minutes > 0)
            .slice()
            .sort((a, b) => (order.get(a.categoryId) ?? 0) - (order.get(b.categoryId) ?? 0));

          return (
            <div key={bucket.key} className={styles.column} title={bucket.title ?? bucket.label}>
              <div className={styles.track}>
                <div className={styles.stack} style={{ height: `${(total / max) * 100}%` }}>
                  {orderedSegments.map((segment) => {
                    const percent = total > 0 ? Math.round((segment.minutes / total) * 100) : 0;
                    const name = nameById.get(segment.categoryId) ?? "Uncategorized";
                    return (
                      <div
                        key={segment.categoryId ?? "uncategorized"}
                        className={styles.segment}
                        style={{
                          flexGrow: segment.minutes,
                          background: categoryColorVar(colorById.get(segment.categoryId)),
                        }}
                        title={`${name}: ${formatDurationMinutes(segment.minutes)} (${percent}%)`}
                      />
                    );
                  })}
                </div>
              </div>
              <span className={styles.label}>{bucket.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
