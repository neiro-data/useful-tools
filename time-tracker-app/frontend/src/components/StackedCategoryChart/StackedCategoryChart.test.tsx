import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  StackedCategoryChart,
  type StackedCategoryBucket,
  type StackedCategoryLegendItem,
} from "./StackedCategoryChart";
import styles from "./StackedCategoryChart.module.css";

const legend: StackedCategoryLegendItem[] = [
  { categoryId: 1, name: "Deep Work", color: "blue" },
  { categoryId: 2, name: "Meetings", color: "orange" },
  { categoryId: null, name: "Uncategorized", color: null },
];

describe("StackedCategoryChart", () => {
  it("renders one legend item per category, ordered as given (desc by total minutes)", () => {
    render(<StackedCategoryChart buckets={[]} legend={legend} />);

    const items = [...document.querySelectorAll(`.${styles.legendItem}`)].map((el) => el.textContent);
    expect(items).toEqual(["Deep Work", "Meetings", "Uncategorized"]);
  });

  it("sizes each segment proportional to its share, and segments sum to the column total", () => {
    const buckets: StackedCategoryBucket[] = [
      {
        key: "day-1",
        label: "Mon",
        segments: [
          { categoryId: 1, minutes: 30 },
          { categoryId: 2, minutes: 90 },
        ],
      },
    ];

    render(<StackedCategoryChart buckets={buckets} legend={legend} />);

    const segments = [...document.querySelectorAll(`.${styles.segment}`)];
    expect(segments).toHaveLength(2);
    // flexGrow is set to each segment's raw minutes, so their sum equals the bucket total and
    // their ratio (30:90 == 1:3) is the proportional split.
    const flexGrows = segments.map((el) => Number((el as HTMLElement).style.flexGrow));
    expect(flexGrows).toEqual([30, 90]);
  });

  it("falls back to the slate token for an uncategorized segment", () => {
    const buckets: StackedCategoryBucket[] = [
      { key: "day-1", label: "Mon", segments: [{ categoryId: null, minutes: 45 }] },
    ];

    render(<StackedCategoryChart buckets={buckets} legend={legend} />);

    const segment = document.querySelector(`.${styles.segment}`) as HTMLElement;
    expect(segment.style.background).toBe("var(--cat-slate)");
  });

  it("carries category name and duration in the segment tooltip", () => {
    const buckets: StackedCategoryBucket[] = [
      { key: "day-1", label: "Mon", segments: [{ categoryId: 1, minutes: 90 }] },
    ];

    render(<StackedCategoryChart buckets={buckets} legend={legend} />);

    const segment = document.querySelector(`.${styles.segment}`) as HTMLElement;
    expect(segment.title).toBe("Deep Work: 1h 30m (100%)");
  });

  it("renders no columns/segments for an empty period", () => {
    render(<StackedCategoryChart buckets={[]} legend={legend} />);

    expect(document.querySelectorAll(`.${styles.column}`)).toHaveLength(0);
    expect(document.querySelectorAll(`.${styles.segment}`)).toHaveLength(0);
  });

  it("omits the legend entirely when it is empty", () => {
    render(<StackedCategoryChart buckets={[]} legend={[]} />);

    expect(document.querySelector(`.${styles.legend}`)).not.toBeInTheDocument();
    expect(screen.queryByText("Deep Work")).not.toBeInTheDocument();
  });
});
