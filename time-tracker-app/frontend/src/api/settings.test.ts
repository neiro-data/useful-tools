import { describe, expect, it, vi } from "vitest";
import { apiRequest } from "./client";
import { getSettings, updateSettings } from "./settings";
import type { SettingsRead } from "./types";

/**
 * `api/settings.ts` tests: `getSettings`/`updateSettings` just delegate to `apiRequest` with the
 * right path/method/body, so `apiRequest` is mocked (no real fetch), mirroring `reports.test.ts`.
 */
vi.mock("./client", () => ({
  apiRequest: vi.fn(),
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

describe("getSettings", () => {
  it("calls apiRequest with the settings path", async () => {
    vi.mocked(apiRequest).mockResolvedValue(makeSettings());

    await getSettings();

    expect(apiRequest).toHaveBeenCalledWith("/settings");
  });
});

describe("updateSettings", () => {
  it("calls apiRequest with PATCH method and the payload as body", async () => {
    const payload = { database_label: "New Label" };
    vi.mocked(apiRequest).mockResolvedValue(makeSettings({ database_label: "New Label" }));

    await updateSettings(payload);

    expect(apiRequest).toHaveBeenCalledWith("/settings", { method: "PATCH", body: payload });
  });
});
