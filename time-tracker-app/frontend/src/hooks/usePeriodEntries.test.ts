import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { usePeriodEntries } from "./usePeriodEntries";
import { listEntries } from "../api/entries";
import type { EntryListResponse, EntryRead } from "../api/types";

/**
 * `usePeriodEntries` fetches *all* entries in `[startDate, endDate]`, paging through
 * `GET /entries` as needed. The `../api/entries` module is mocked so no real fetch happens.
 */
vi.mock("../api/entries", () => ({
  listEntries: vi.fn(),
}));

function makeEntry(overrides: Partial<EntryRead> = {}): EntryRead {
  return {
    id: 1,
    title: "Deep Work",
    notes: null,
    category: null,
    tags: [],
    start_ts: "2026-07-06T09:00:00Z",
    end_ts: "2026-07-06T10:00:00Z",
    duration_minutes: 60,
    entry_mode: "manual",
    created_at: "2026-07-06T10:00:00Z",
    updated_at: "2026-07-06T10:00:00Z",
    ...overrides,
  };
}

function makePage(items: EntryRead[], total: number, offset = 0, limit = 200): EntryListResponse {
  return { items, total, limit, offset };
}

describe("usePeriodEntries", () => {
  it("fetches a single page and resolves loading with no error", async () => {
    const entries = [makeEntry(), makeEntry({ id: 2 })];
    vi.mocked(listEntries).mockResolvedValue(makePage(entries, entries.length));

    const { result } = renderHook(() => usePeriodEntries("2026-07-06", "2026-07-12"));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.entries).toEqual(entries);
    expect(result.current.error).toBeNull();
  });

  it("sets error and stops loading when a request rejects", async () => {
    vi.mocked(listEntries).mockRejectedValue(new Error("Network down"));

    const { result } = renderHook(() => usePeriodEntries("2026-07-06", "2026-07-12"));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe("Network down");
  });

  it("does not update state when reload() resolves after unmount", async () => {
    const entries = [makeEntry()];
    vi.mocked(listEntries).mockResolvedValue(makePage(entries, entries.length));

    const { result, unmount } = renderHook(() => usePeriodEntries("2026-07-06", "2026-07-12"));
    await waitFor(() => expect(result.current.loading).toBe(false));

    let resolvePage: (value: EntryListResponse) => void = () => {};
    vi.mocked(listEntries).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolvePage = resolve;
        }),
    );

    const reloadPromise = result.current.reload();
    unmount();

    // Resolving after unmount must not trigger a setState-on-unmounted-component warning/write.
    await act(async () => {
      resolvePage(makePage([makeEntry({ id: 3 })], 1));
      await reloadPromise;
    });
  });
});
