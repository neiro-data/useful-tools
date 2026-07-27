import { render, screen, fireEvent, act } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { WeekPage } from "./WeekPage";
import { usePeriodEntries } from "../../hooks/usePeriodEntries";
import { useRunningTimer } from "../../hooks/useRunningTimer";
import { listCategories } from "../../api/categories";
import { listTags } from "../../api/tags";
import { updateEntry } from "../../api/entries";
import type { CategoryRead, EntryRead } from "../../api/types";

/**
 * Mirrors `MonthPage.test.tsx`'s convention: mock the data-fetching hooks/calls directly rather
 * than the network, since `WeekPage` renders whatever they return and aggregates client-side.
 */
vi.mock("../../hooks/usePeriodEntries", () => ({
  usePeriodEntries: vi.fn(),
}));
vi.mock("../../hooks/useRunningTimer", () => ({
  useRunningTimer: vi.fn(),
}));
vi.mock("../../api/categories", () => ({
  listCategories: vi.fn(),
}));
vi.mock("../../api/tags", () => ({
  listTags: vi.fn(),
}));
vi.mock("../../api/entries", async () => {
  const actual = await vi.importActual<typeof import("../../api/entries")>("../../api/entries");
  return { ...actual, updateEntry: vi.fn() };
});

const deepWork: CategoryRead = { id: 1, name: "Deep Work", color: "blue", is_active: true, sort_order: 0 };

function makeEntry(overrides: Partial<EntryRead>): EntryRead {
  return {
    id: 1,
    title: "Entry",
    notes: null,
    category: deepWork,
    tags: [],
    start_ts: "2026-06-15T09:00:00+00:00",
    end_ts: "2026-06-15T10:00:00+00:00",
    duration_minutes: 60,
    entry_mode: "manual",
    created_at: "2026-06-15T09:00:00+00:00",
    updated_at: "2026-06-15T09:00:00+00:00",
    ...overrides,
  };
}

function mockHooks(entries: EntryRead[]): void {
  vi.mocked(usePeriodEntries).mockReturnValue({
    entries,
    loading: false,
    error: null,
    reload: vi.fn().mockResolvedValue(undefined),
  });
  vi.mocked(useRunningTimer).mockReturnValue({
    runningTimer: null,
    loading: false,
    refresh: vi.fn().mockResolvedValue(undefined),
    stop: vi.fn().mockResolvedValue(undefined),
  });
  vi.mocked(listCategories).mockResolvedValue({ items: [], total: 0 });
  vi.mocked(listTags).mockResolvedValue({ items: [], total: 0 });
}

describe("WeekPage", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 5, 15, 12, 0, 0));
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("regression: forwards tag_ids and start_ts to updateEntry when saving an edited entry", async () => {
    // Previously `handleSaveEntry` called `updateEntry` WITHOUT `tag_ids`/`start_ts`, so tag edits
    // made on Week silently never persisted. This pins the fix.
    const focusTag = { id: 5, name: "focus", is_active: true };
    const entry = makeEntry({ id: 42, tags: [] });
    mockHooks([entry]);
    vi.mocked(listTags).mockResolvedValue({ items: [focusTag], total: 1 });
    vi.mocked(updateEntry).mockResolvedValue(entry);

    render(<WeekPage />);
    await act(async () => {
      await Promise.resolve();
    });

    fireEvent.click(screen.getByTestId("entry-row"));
    fireEvent.change(screen.getByLabelText("Add tag"), { target: { value: "focus" } });
    fireEvent.keyDown(screen.getByLabelText("Add tag"), { key: "Enter" });
    fireEvent.click(screen.getByText("Save"));

    await vi.waitFor(() =>
      expect(updateEntry).toHaveBeenCalledWith(
        42,
        expect.objectContaining({
          tag_ids: [focusTag.id],
          start_ts: new Date(entry.start_ts).toISOString(),
        }),
      ),
    );
  });
});
