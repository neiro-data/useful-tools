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

  it("renders the bucket's total duration as a label above the column (absorbed from MiniBarChart)", () => {
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

    const value = document.querySelector(`.${styles.value}`);
    expect(value?.textContent).toBe("2h 00m");
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

  it("renders a zero total ('0m') and no segments for a bucket with no logged time", () => {
    const buckets: StackedCategoryBucket[] = [{ key: "day-1", label: "Mon", segments: [] }];

    render(<StackedCategoryChart buckets={buckets} legend={legend} />);

    const value = document.querySelector(`.${styles.value}`);
    expect(value?.textContent).toBe("0m");
    expect(document.querySelectorAll(`.${styles.segment}`)).toHaveLength(0);
  });

  it("gives `.columns` no flex gap, so each of the N `.column`s occupies exactly 1/N of the width", () => {
    const buckets: StackedCategoryBucket[] = [
      { key: "day-1", label: "Mon", segments: [{ categoryId: 1, minutes: 30 }] },
      { key: "day-2", label: "Tue", segments: [{ categoryId: 1, minutes: 30 }] },
      { key: "day-3", label: "Wed", segments: [{ categoryId: 1, minutes: 30 }] },
      { key: "day-4", label: "Thu", segments: [{ categoryId: 1, minutes: 30 }] },
    ];

    render(<StackedCategoryChart buckets={buckets} legend={legend} />);

    const columnsEl = document.querySelector(`.${styles.columns}`) as HTMLElement;
    // No gap here matters because CountLineChart centres point i at ((i + 0.5) / N) * 100% of the
    // plot width; a gap on `.columns` would shrink/offset each `flex: 1` column and break that
    // alignment between the two charts' buckets. See the CSS comment above `.columns`.
    // jsdom's `getComputedStyle` doesn't resolve inherited/initial values, so an unset `gap`
    // computes to "" rather than "0px" — contrast with `.legend`/`.chart` (both set `gap` in this
    // module's CSS), which do resolve to a token value.
    expect(getComputedStyle(columnsEl).gap).toBe("");
    expect(document.querySelectorAll(`.${styles.column}`)).toHaveLength(4);
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
