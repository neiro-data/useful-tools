import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MiniBarChart } from "./MiniBarChart";
import styles from "./MiniBarChart.module.css";
import type { MiniBarChartBar } from "./bars";

/**
 * `MiniBarChart` renders one column per bar plus label-thinning for long ranges — covered
 * directly against hand-built `bars` (no need to go through `barsFromDays`/`barsFromWeeks`).
 */

function makeBars(count: number, minutesFor: (index: number) => number = () => 30): MiniBarChartBar[] {
  return Array.from({ length: count }, (_, index) => ({
    key: `bar-${index}`,
    label: `L${index}`,
    minutes: minutesFor(index),
  }));
}

describe("MiniBarChart", () => {
  it("renders one column with a value and label per bar", () => {
    const bars: MiniBarChartBar[] = [
      { key: "mon", label: "Mon", minutes: 60 },
      { key: "tue", label: "Tue", minutes: 90 },
    ];

    const { container } = render(<MiniBarChart bars={bars} />);

    expect(screen.getByText("Mon")).toBeInTheDocument();
    expect(screen.getByText("Tue")).toBeInTheDocument();
    expect(screen.getByText("1h 00m")).toBeInTheDocument();
    expect(screen.getByText("1h 30m")).toBeInTheDocument();
    expect(container.querySelectorAll(`.${styles.column}`)).toHaveLength(2);
  });

  it("renders a hairline (not a bar) for a zero-minute bucket, with no inline height", () => {
    const bars: MiniBarChartBar[] = [
      { key: "mon", label: "Mon", minutes: 0 },
      { key: "tue", label: "Tue", minutes: 60 },
    ];

    const { container } = render(<MiniBarChart bars={bars} />);

    const columns = container.querySelectorAll(`.${styles.column}`);
    const zeroTrack = columns[0]?.querySelector(`.${styles.track}`);
    const zeroChild = zeroTrack?.firstElementChild as HTMLElement;
    expect(zeroChild.className).toContain(styles.hairline);
    expect(zeroChild.style.height).toBe("");

    const nonZeroTrack = columns[1]?.querySelector(`.${styles.track}`);
    const nonZeroChild = nonZeroTrack?.firstElementChild as HTMLElement;
    expect(nonZeroChild.className).toContain(styles.bar);
    expect(nonZeroChild.style.height).toBe("100%");
  });

  it("keeps every label for a week-length (7 bars or fewer) range", () => {
    const bars = makeBars(7);

    const { container } = render(<MiniBarChart bars={bars} />);

    const labels = [...container.querySelectorAll(`.${styles.label}`)].map((el) => el.textContent);
    expect(labels).toEqual(bars.map((bar) => bar.label));
  });

  it("thins labels for a long range, always keeping the first and last", () => {
    const bars = makeBars(30);

    const { container } = render(<MiniBarChart bars={bars} />);

    const labels = [...container.querySelectorAll(`.${styles.label}`)].map((el) => el.textContent);
    expect(labels).toHaveLength(30);
    expect(labels[0]).toBe("L0");
    expect(labels[labels.length - 1]).toBe("L29");

    const shownCount = labels.filter((label) => label !== " ").length;
    // ~8 labels across a long range, regardless of total length.
    expect(shownCount).toBeGreaterThanOrEqual(7);
    expect(shownCount).toBeLessThanOrEqual(10);

    // A label in the middle that doesn't land on the thinning step is blanked, not dropped.
    expect(labels[2]).toBe(" ");
  });
});
