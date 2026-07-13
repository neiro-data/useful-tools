import type { ReactElement } from "react";
import styles from "./Skeleton.module.css";

interface SkeletonProps {
  height?: number;
  width?: string;
}

/** Layout-matching loading placeholder (`design/screens.md` §1.7/§2.3): no spinner, skeletons
 * match the final layout so there's no reflow once data arrives. Respects
 * `prefers-reduced-motion` via the global rule in `design/tokens.css`. */
export function Skeleton({ height = 40, width = "100%" }: SkeletonProps): ReactElement {
  return <div className={styles.skeleton} style={{ height, width }} aria-hidden="true" />;
}
