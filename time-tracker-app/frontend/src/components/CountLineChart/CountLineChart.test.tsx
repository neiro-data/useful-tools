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

    expect(container.querySelectorAll("circle")).toHaveLength(3);
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

    expect(container.querySelectorAll("circle")).toHaveLength(1);
    expect(container.querySelector("polyline")).not.toBeInTheDocument();
  });

  it("renders a flat baseline (all markers at the same height) when every count is zero", () => {
    const points: CountLineChartPoint[] = [
      { key: "d1", label: "Mon", count: 0 },
      { key: "d2", label: "Tue", count: 0 },
      { key: "d3", label: "Wed", count: 0 },
    ];

    const { container } = render(<CountLineChart points={points} />);

    const ys = [...container.querySelectorAll("circle")].map((el) => el.getAttribute("cy"));
    expect(new Set(ys).size).toBe(1);
  });

  it("renders nothing for zero points", () => {
    const { container } = render(<CountLineChart points={[]} />);

    expect(container.querySelector("svg")).not.toBeInTheDocument();
    expect(container.querySelector(`.${styles.chart}`)).toBeInTheDocument();
  });
});
