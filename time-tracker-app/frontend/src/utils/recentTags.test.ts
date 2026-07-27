import { describe, expect, it } from "vitest";
import { recentTagsFromEntries } from "./recentTags";
import type { EntryRead, TagRead } from "../api/types";

const focus: TagRead = { id: 1, name: "focus", is_active: true };
const urgent: TagRead = { id: 2, name: "urgent", is_active: true };
const bug: TagRead = { id: 3, name: "bug", is_active: true };

function makeEntry(overrides: Partial<EntryRead>): EntryRead {
  return {
    id: 1,
    title: "Entry",
    notes: null,
    category: { id: 1, name: "Deep Work", color: "blue", is_active: true, sort_order: 0 },
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

describe("recentTagsFromEntries", () => {
  it("orders tags most-recent-first by entry start_ts", () => {
    const entries = [
      makeEntry({ id: 1, start_ts: "2026-07-13T09:00:00+00:00", tags: [focus] }),
      makeEntry({ id: 2, start_ts: "2026-07-14T09:00:00+00:00", tags: [urgent] }),
    ];

    expect(recentTagsFromEntries(entries).map((t) => t.id)).toEqual([urgent.id, focus.id]);
  });

  it("dedupes a tag used on multiple entries, keeping only its most recent use in the ordering", () => {
    const entries = [
      makeEntry({ id: 1, start_ts: "2026-07-10T09:00:00+00:00", tags: [focus] }),
      makeEntry({ id: 2, start_ts: "2026-07-14T09:00:00+00:00", tags: [urgent, focus] }),
    ];

    const result = recentTagsFromEntries(entries);
    expect(result.map((t) => t.id)).toEqual([urgent.id, focus.id]);
  });

  it("caps the result at the given limit", () => {
    const entries = [makeEntry({ id: 1, tags: [focus, urgent, bug] })];

    expect(recentTagsFromEntries(entries, 2)).toHaveLength(2);
  });

  it("returns an empty array for no entries", () => {
    expect(recentTagsFromEntries([])).toEqual([]);
  });
});
