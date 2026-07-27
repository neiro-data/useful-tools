import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CountLineChart, type CountLineChartPoint } from "./CountLineChart";
import styles from "./CountLineChart.module.css";

describe("CountLineChart", () => {
  it("renders one marker per bucket, matching the point count", () => {
    const points: CountLineChartPoint[] = [
      { key: "d1", label: "Mon", count: 2 },
      { key: "d2", label: "Tue", count: 0 },
      { key: "d3", label: "Wed", count: 5 },
    ];

    const { container } = render(<CountLineChart points={points} />);

    // Markers are plain HTML elements (not SVG `<circle>`s) so they stay round under the
    // polyline's non-uniform `preserveAspectRatio="none"` scaling.
    expect(container.querySelectorAll(`.${styles.marker}`)).toHaveLength(3);
  });

  it("renders a polyline connecting the points when there is more than one", () => {
    const points: CountLineChartPoint[] = [
      { key: "d1", label: "Mon", count: 2 },
      { key: "d2", label: "Tue", count: 4 },
    ];

    const { container } = render(<CountLineChart points={points} />);

    expect(container.querySelector("polyline")).toBeInTheDocument();
  });

  it("renders a single dot with no polyline for a single point", () => {
    const points: CountLineChartPoint[] = [{ key: "d1", label: "Mon", count: 3 }];

    const { container } = render(<CountLineChart points={points} />);

    expect(container.querySelectorAll(`.${styles.marker}`)).toHaveLength(1);
    expect(container.querySelector("polyline")).not.toBeInTheDocument();
  });

  it("renders a flat baseline (all markers at the same height) when every count is zero", () => {
    const points: CountLineChartPoint[] = [
      { key: "d1", label: "Mon", count: 0 },
      { key: "d2", label: "Tue", count: 0 },
      { key: "d3", label: "Wed", count: 0 },
    ];

    const { container } = render(<CountLineChart points={points} />);

    const tops = [...container.querySelectorAll(`.${styles.point}`)].map(
      (el) => (el as HTMLElement).style.top,
    );
    expect(new Set(tops).size).toBe(1);
  });

  it("renders nothing for zero points", () => {
    const { container } = render(<CountLineChart points={[]} />);

    expect(container.querySelector("svg")).not.toBeInTheDocument();
    expect(container.querySelector(`.${styles.chart}`)).toBeInTheDocument();
  });

  it("centres each point at (index + 0.5)/N of the plot width, matching StackedCategoryChart's column centring", () => {
    const points: CountLineChartPoint[] = [
      { key: "d1", label: "Mon", count: 1 },
      { key: "d2", label: "Tue", count: 2 },
      { key: "d3", label: "Wed", count: 3 },
      { key: "d4", label: "Thu", count: 4 },
    ];

    const { container } = render(<CountLineChart points={points} />);

    const lefts = [...container.querySelectorAll(`.${styles.point}`)].map(
      (el) => (el as HTMLElement).style.left,
    );
    // 4 points -> slot centres at 12.5%, 37.5%, 62.5%, 87.5%.
    expect(lefts).toEqual(["12.5%", "37.5%", "62.5%", "87.5%"]);
  });

  it("centres a single point at 50% (N=1), not dividing by zero", () => {
    const points: CountLineChartPoint[] = [{ key: "d1", label: "Mon", count: 3 }];

    const { container } = render(<CountLineChart points={points} />);

    const point = container.querySelector(`.${styles.point}`) as HTMLElement;
    expect(point.style.left).toBe("50%");
  });

  it("keeps the tallest point's label from touching the plot top (TOP_HEADROOM reserved above it)", () => {
    const points: CountLineChartPoint[] = [
      { key: "d1", label: "Mon", count: 1 },
      { key: "d2", label: "Tue", count: 10 },
    ];

    const { container } = render(<CountLineChart points={points} />);

    const tops = [...container.querySelectorAll(`.${styles.point}`)].map(
      (el) => Number.parseFloat((el as HTMLElement).style.top),
    );
    // The max-count point maps to y = TOP_HEADROOM (22), not 0 — headroom is reserved above it so
    // its count label isn't clipped by the plot box's top edge.
    expect(Math.min(...tops)).toBeCloseTo(22, 5);
  });

  it("renders each point's count as a visible label above the marker", () => {
    const points: CountLineChartPoint[] = [
      { key: "d1", label: "Mon", count: 2 },
      { key: "d2", label: "Tue", count: 7 },
    ];

    const { container } = render(<CountLineChart points={points} />);

    const labels = [...container.querySelectorAll(`.${styles.countLabel}`)].map((el) => el.textContent);
    expect(labels).toEqual(["2", "7"]);
  });

  it("anchors the marker (not a label+marker stack) on the point's own coordinate", () => {
    // Regression guard: `.point` used to be a centred flex column of [label, marker], which shifts
    // the marker below the (x, y) coordinate the polyline is drawn through by roughly half the
    // label's height. `.point` must now be a zero-size, untransformed anchor, with only `.marker`
    // itself centred on that coordinate via its own transform.
    const points: CountLineChartPoint[] = [{ key: "d1", label: "Mon", count: 3 }];

    const { container } = render(<CountLineChart points={points} />);

    const point = container.querySelector(`.${styles.point}`) as HTMLElement;
    const marker = container.querySelector(`.${styles.marker}`) as HTMLElement;

    expect(getComputedStyle(point).transform).toBe("none");
    expect(getComputedStyle(marker).transform).not.toBe("none");
  });

  it("carries the tooltip on the marker element (not an SVG <title>)", () => {
    const points: CountLineChartPoint[] = [{ key: "d1", label: "Mon", title: "Monday, Jul 6", count: 3 }];

    const { container } = render(<CountLineChart points={points} />);

    const marker = container.querySelector(`.${styles.marker}`) as HTMLElement;
    expect(marker.title).toBe("Monday, Jul 6: 3 entries");
  });
});
