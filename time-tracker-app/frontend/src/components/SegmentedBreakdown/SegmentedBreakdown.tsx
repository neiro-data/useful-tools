import { useState, type CSSProperties, type ReactElement } from "react";
import type { BreakdownSegment } from "../../utils/aggregate";
import { formatDurationMinutes } from "../../utils/duration";
import { categoryColorVar, categoryChipTint } from "../../utils/categoryColor";
import styles from "./SegmentedBreakdown.module.css";

interface SegmentedBreakdownProps {
  title: string;
  segments: BreakdownSegment[];
  /** `"category"` renders each segment/legend dot in its `--cat-*` color; `"tag"` renders a flat
   * neutral grayscale (opacity steps) per `design/DESIGN_SYSTEM.md` §8.8. */
  variant: "category" | "tag";
  /** Tag breakdowns show only the top N with a "+N more" expander; category shows all. */
  visibleLimit?: number;
  emptyLabel?: string;
}

/** Shared segmented-bar + legend pattern (§8.8), reused for Week's and Month's by-category and
 * by-tag breakdowns. */
export function SegmentedBreakdown({
  title,
  segments,
  variant,
  visibleLimit,
  emptyLabel = "No data yet — entries you log will show up here.",
}: SegmentedBreakdownProps): ReactElement {
  const [expanded, setExpanded] = useState(false);
  const visible = visibleLimit && !expanded ? segments.slice(0, visibleLimit) : segments;
  const hiddenCount = visibleLimit ? Math.max(0, segments.length - visibleLimit) : 0;

  return (
    <section className={styles.section} aria-label={title}>
      <h3 className={styles.heading}>{title}</h3>
      {segments.length === 0 ? (
        <p className={styles.empty}>{emptyLabel}</p>
      ) : (
        <>
          <div className={styles.bar} role="img" aria-hidden="true">
            {segments.map((segment, index) => (
              <span
                key={segment.key}
                className={styles.segment}
                style={segmentStyle(segment, variant, index)}
              />
            ))}
          </div>
          <ul className={styles.legend}>
            {visible.map((segment, index) => (
              <li key={segment.key} className={styles.legendItem}>
                <span
                  className={styles.dot}
                  style={{ background: dotColor(segment, variant, index) }}
                  aria-hidden="true"
                />
                <span className={styles.legendLabel}>{segment.label}</span>
                <span className={styles.legendDuration}>{formatDurationMinutes(segment.minutes)}</span>
                <span className={styles.legendPercent}>{Math.round(segment.percent)}%</span>
              </li>
            ))}
          </ul>
          {hiddenCount > 0 && (
            <button type="button" className={styles.moreButton} onClick={() => setExpanded(true)}>
              + {hiddenCount} more {variant === "tag" ? "tags" : "categories"}
            </button>
          )}
        </>
      )}
    </section>
  );
}

function segmentStyle(segment: BreakdownSegment, variant: "category" | "tag", index: number): CSSProperties {
  if (variant === "category") {
    return {
      flexGrow: segment.percent || 0.001,
      background: categoryChipTint(segment.colorKey),
      borderRight: `1px solid ${categoryColorVar(segment.colorKey)}`,
    };
  }
  const opacity = Math.max(0.15, 1 - index * 0.15);
  return {
    flexGrow: segment.percent || 0.001,
    background: `color-mix(in srgb, var(--color-text-muted) ${opacity * 100}%, transparent)`,
    borderRight: "1px solid var(--color-border-strong)",
  };
}

function dotColor(segment: BreakdownSegment, variant: "category" | "tag", index: number): string {
  if (variant === "category") return categoryColorVar(segment.colorKey);
  const opacity = Math.max(0.3, 1 - index * 0.15);
  return `color-mix(in srgb, var(--color-text-muted) ${opacity * 100}%, transparent)`;
}
