import { describe, expect, it } from "vitest";
import { breakdownByCategory, breakdownByTag, totalMinutes } from "./aggregate";
import type { CategoryRead, EntryRead, TagRead } from "../api/types";

/**
 * `utils/aggregate.ts` backs both the Week and Month pages' totals-by-category and
 * totals-by-tag breakdowns, so its summation logic is high-value to cover directly against a
 * fixed set of entries (no rendering involved).
 */

const deepWork: CategoryRead = {
  id: 1,
  name: "Deep Work",
  color: "blue",
  is_active: true,
  sort_order: 0,
};

const meetings: CategoryRead = {
  id: 2,
  name: "Meetings",
  color: "amber",
  is_active: true,
  sort_order: 1,
};

const focusTag: TagRead = { id: 10, name: "focus", is_active: true };
const urgentTag: TagRead = { id: 11, name: "urgent", is_active: true };

function makeEntry(overrides: Partial<EntryRead>): EntryRead {
  return {
    id: 1,
    title: "Entry",
    notes: null,
    category: null,
    tags: [],
    start_ts: "2026-07-13T09:00:00+00:00",
    end_ts: "2026-07-13T10:00:00+00:00",
    duration_minutes: 60,
    entry_mode: "manual",
    created_at: "2026-07-13T09:00:00+00:00",
    updated_at: "2026-07-13T09:00:00+00:00",
    ...overrides,
  };
}

describe("totalMinutes", () => {
  it("sums duration_minutes across entries, treating a null duration (running timer) as zero", () => {
    const entries = [
      makeEntry({ id: 1, duration_minutes: 30 }),
      makeEntry({ id: 2, duration_minutes: 45 }),
      makeEntry({ id: 3, duration_minutes: null }),
    ];

    expect(totalMinutes(entries)).toBe(75);
  });
});

describe("breakdownByCategory", () => {
  it("sums minutes per category, including an Uncategorized bucket, sorted descending", () => {
    const entries = [
      makeEntry({ id: 1, category: deepWork, duration_minutes: 60 }),
      makeEntry({ id: 2, category: deepWork, duration_minutes: 30 }),
      makeEntry({ id: 3, category: meetings, duration_minutes: 20 }),
      makeEntry({ id: 4, category: null, duration_minutes: 10 }),
    ];

    const breakdown = breakdownByCategory(entries);

    expect(breakdown).toHaveLength(3);
    expect(breakdown[0]).toMatchObject({ key: "cat-1", label: "Deep Work", minutes: 90 });
    expect(breakdown[1]).toMatchObject({ key: "cat-2", label: "Meetings", minutes: 20 });
    expect(breakdown[2]).toMatchObject({ key: "uncategorized", label: "Uncategorized", minutes: 10 });

    const grandTotal = 90 + 20 + 10;
    expect(breakdown[0]?.percent).toBeCloseTo((90 / grandTotal) * 100);
    expect(breakdown[2]?.percent).toBeCloseTo((10 / grandTotal) * 100);
  });

  it("returns an empty list for no entries", () => {
    expect(breakdownByCategory([])).toEqual([]);
  });
});

describe("breakdownByTag", () => {
  it("sums minutes per tag, double-counting an entry that carries multiple tags, plus an Untagged bucket", () => {
    const entries = [
      makeEntry({ id: 1, tags: [focusTag, urgentTag], duration_minutes: 40 }),
      makeEntry({ id: 2, tags: [focusTag], duration_minutes: 20 }),
      makeEntry({ id: 3, tags: [], duration_minutes: 15 }),
    ];

    const breakdown = breakdownByTag(entries);
    const byKey = Object.fromEntries(breakdown.map((segment) => [segment.key, segment]));

    expect(byKey["tag-10"]).toMatchObject({ label: "#focus", minutes: 60 });
    expect(byKey["tag-11"]).toMatchObject({ label: "#urgent", minutes: 40 });
    expect(byKey["untagged"]).toMatchObject({ label: "Untagged", minutes: 15 });

    // percent is computed against the grand total of tag-minutes (which double-counts
    // multi-tagged entries by design, since a segment exists per tag).
    const grandTotal = 60 + 40 + 15;
    expect(byKey["tag-10"]?.percent).toBeCloseTo((60 / grandTotal) * 100);
  });

  it("treats a null duration_minutes (running timer) as contributing zero minutes", () => {
    const entries = [makeEntry({ id: 1, tags: [focusTag], duration_minutes: null })];

    const breakdown = breakdownByTag(entries);

    expect(breakdown).toEqual([
      { key: "tag-10", label: "#focus", colorKey: null, minutes: 0, percent: 0 },
    ]);
  });
});
