import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useSettings } from "./useSettings";
import { getSettings, updateSettings } from "../api/settings";
import type { SettingsRead } from "../api/types";

/**
 * `useSettings` fetches `GET /settings` on mount and exposes a `save` helper backed by
 * `PATCH /settings`. The `../api/settings` module is mocked so no real fetch happens.
 */
vi.mock("../api/settings", () => ({
  getSettings: vi.fn(),
  updateSettings: vi.fn(),
}));

function makeSettings(overrides: Partial<SettingsRead> = {}): SettingsRead {
  return {
    id: 1,
    default_entry_mode: "timer",
    week_starts_on: "monday",
    default_export_format: "html",
    database_label: "My Database",
    timezone: "UTC",
    ...overrides,
  };
}

describe("useSettings", () => {
  it("fetches settings on mount and resolves loading with no error", async () => {
    const settings = makeSettings();
    vi.mocked(getSettings).mockResolvedValue(settings);

    const { result } = renderHook(() => useSettings());

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.settings).toEqual(settings);
    expect(result.current.error).toBeNull();
    expect(getSettings).toHaveBeenCalled();
  });

  it("sets error and stops loading when the initial fetch rejects", async () => {
    vi.mocked(getSettings).mockRejectedValue(new Error("Network down"));

    const { result } = renderHook(() => useSettings());

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe("Network down");
    expect(result.current.settings).toBeNull();
  });

  it("save() calls updateSettings and updates settings from the response", async () => {
    vi.mocked(getSettings).mockResolvedValue(makeSettings());
    const updated = makeSettings({ database_label: "New Label" });
    vi.mocked(updateSettings).mockResolvedValue(updated);

    const { result } = renderHook(() => useSettings());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.save({ database_label: "New Label" });
    });

    expect(updateSettings).toHaveBeenCalledWith({ database_label: "New Label" });
    expect(result.current.settings).toEqual(updated);
  });

  it("save() rethrows the error on failure without updating settings", async () => {
    const settings = makeSettings();
    vi.mocked(getSettings).mockResolvedValue(settings);
    const failure = new Error("Save failed");
    vi.mocked(updateSettings).mockRejectedValue(failure);

    const { result } = renderHook(() => useSettings());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await expect(
      act(async () => {
        await result.current.save({ database_label: "Bad" });
      }),
    ).rejects.toThrow("Save failed");

    expect(result.current.settings).toEqual(settings);
  });
});
