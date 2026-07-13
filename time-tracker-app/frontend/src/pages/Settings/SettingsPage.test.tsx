import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SettingsPage } from "./SettingsPage";
import { useSettings } from "../../hooks/useSettings";
import { ApiError } from "../../api/errors";
import type { SettingsRead } from "../../api/types";

/**
 * `SettingsPage` renders a form prefilled from whatever `useSettings` returns and calls its
 * `save` helper on submit — so the hook is mocked directly rather than the underlying API calls,
 * mirroring `ReportsPage.test.tsx`.
 */
vi.mock("../../hooks/useSettings", () => ({
  useSettings: vi.fn(),
}));

function makeSettings(overrides: Partial<SettingsRead> = {}): SettingsRead {
  return {
    id: 1,
    default_entry_mode: "timer",
    week_starts_on: "monday",
    default_export_format: "html",
    database_label: "My Database",
    timezone: "Europe/Lisbon",
    ...overrides,
  };
}

function mockHook(overrides: Partial<ReturnType<typeof useSettings>> = {}): void {
  vi.mocked(useSettings).mockReturnValue({
    settings: makeSettings(),
    loading: false,
    error: null,
    reload: vi.fn().mockResolvedValue(undefined),
    save: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  });
}

describe("SettingsPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the form prefilled with the current settings", () => {
    mockHook();

    render(<SettingsPage />);

    expect(screen.getByLabelText("Default entry mode")).toHaveValue("timer");
    expect(screen.getByLabelText("Week starts on")).toHaveValue("monday");
    expect(screen.getByLabelText("Default export format")).toHaveValue("html");
    expect(screen.getByLabelText("Database label")).toHaveValue("My Database");
    expect(screen.getByLabelText("Timezone")).toHaveValue("Europe/Lisbon");
  });

  it("shows skeleton placeholders while loading", () => {
    mockHook({ loading: true, settings: null });

    const { container } = render(<SettingsPage />);

    expect(screen.queryByLabelText("Database label")).not.toBeInTheDocument();
    expect(container.querySelectorAll('[aria-hidden="true"]').length).toBeGreaterThan(0);
  });

  it("shows the error banner when the initial load failed", () => {
    mockHook({ error: "Failed to load settings.", settings: null });

    render(<SettingsPage />);

    expect(screen.getByRole("alert")).toHaveTextContent("Failed to load settings.");
  });

  it("shows a success banner after a successful save with changed fields", async () => {
    const save = vi.fn().mockResolvedValue(undefined);
    mockHook({ save });

    render(<SettingsPage />);

    fireEvent.change(screen.getByLabelText("Database label"), {
      target: { value: "Renamed Database" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Settings saved."));

    expect(save).toHaveBeenCalledWith({ database_label: "Renamed Database" });
  });

  it("shows the error banner when the save fails", async () => {
    const save = vi.fn().mockRejectedValue(new ApiError(400, "validation_error", "Invalid timezone."));
    mockHook({ save });

    render(<SettingsPage />);

    fireEvent.change(screen.getByLabelText("Timezone"), {
      target: { value: "Not/AZone" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Invalid timezone."));
  });

  it("disables the Save button when the database label is blank", () => {
    mockHook();

    render(<SettingsPage />);

    fireEvent.change(screen.getByLabelText("Database label"), { target: { value: "   " } });

    expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled();
  });

  it("disables the Save button when the timezone is blank", () => {
    mockHook();

    render(<SettingsPage />);

    fireEvent.change(screen.getByLabelText("Timezone"), { target: { value: "" } });

    expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled();
  });
});
