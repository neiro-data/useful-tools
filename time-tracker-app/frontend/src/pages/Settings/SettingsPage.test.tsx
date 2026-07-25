import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SettingsPage } from "./SettingsPage";
import { useSettings } from "../../hooks/useSettings";
import { useTimezones } from "../../hooks/useTimezones";
import { useCategories } from "../../hooks/useCategories";
import { createCategory } from "../../api/categories";
import { ApiError } from "../../api/errors";
import type { CategoryRead, SettingsRead } from "../../api/types";

/**
 * `SettingsPage` renders a form prefilled from whatever `useSettings`/`useTimezones`/
 * `useCategories` return, and calls `save` / `createCategory` — so those hooks/functions are
 * mocked directly rather than the underlying `fetch` calls, mirroring `ReportsPage.test.tsx`.
 */
vi.mock("../../hooks/useSettings", () => ({
  useSettings: vi.fn(),
}));
vi.mock("../../hooks/useTimezones", () => ({
  useTimezones: vi.fn(),
}));
vi.mock("../../hooks/useCategories", () => ({
  useCategories: vi.fn(),
}));
vi.mock("../../api/categories", () => ({
  createCategory: vi.fn(),
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

function makeCategory(overrides: Partial<CategoryRead> = {}): CategoryRead {
  return {
    id: 1,
    name: "Deep Work",
    color: "blue",
    is_active: true,
    sort_order: 0,
    ...overrides,
  };
}

function mockSettingsHook(overrides: Partial<ReturnType<typeof useSettings>> = {}): void {
  vi.mocked(useSettings).mockReturnValue({
    settings: makeSettings(),
    loading: false,
    error: null,
    reload: vi.fn().mockResolvedValue(undefined),
    save: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  });
}

function mockTimezonesHook(overrides: Partial<ReturnType<typeof useTimezones>> = {}): void {
  vi.mocked(useTimezones).mockReturnValue({
    timezones: [
      { name: "Europe/Lisbon", utc_offset: "+01:00" },
      { name: "Europe/Madrid", utc_offset: "+02:00" },
      { name: "America/New_York", utc_offset: "-04:00" },
    ],
    loading: false,
    error: null,
    ...overrides,
  });
}

function mockCategoriesHook(overrides: Partial<ReturnType<typeof useCategories>> = {}): void {
  vi.mocked(useCategories).mockReturnValue({
    categories: [makeCategory()],
    loading: false,
    error: null,
    reload: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  });
}

describe("SettingsPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.mocked(createCategory).mockReset();
  });

  it("renders the form prefilled with the current settings", () => {
    mockSettingsHook();
    mockTimezonesHook();
    mockCategoriesHook();

    render(<SettingsPage />);

    expect(screen.getByLabelText("Default entry mode")).toHaveValue("timer");
    expect(screen.getByLabelText("Week starts on")).toHaveValue("monday");
    expect(screen.getByLabelText("Default export format")).toHaveValue("html");
    expect(screen.getByLabelText("Database label")).toHaveValue("My Database");
    expect(screen.getByLabelText("Timezone")).toHaveValue("Europe/Lisbon");
  });

  it("shows skeleton placeholders while loading", () => {
    mockSettingsHook({ loading: true, settings: null });
    mockTimezonesHook();
    mockCategoriesHook();

    const { container } = render(<SettingsPage />);

    expect(screen.queryByLabelText("Database label")).not.toBeInTheDocument();
    expect(container.querySelectorAll('[aria-hidden="true"]').length).toBeGreaterThan(0);
  });

  it("shows the error banner when the initial load failed", () => {
    mockSettingsHook({ error: "Failed to load settings.", settings: null });
    mockTimezonesHook();
    mockCategoriesHook();

    render(<SettingsPage />);

    expect(screen.getByRole("alert")).toHaveTextContent("Failed to load settings.");
  });

  it("shows a success banner after a successful save with changed fields", async () => {
    const save = vi.fn().mockResolvedValue(undefined);
    mockSettingsHook({ save });
    mockTimezonesHook();
    mockCategoriesHook();

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
    mockSettingsHook({ save });
    mockTimezonesHook();
    mockCategoriesHook();

    render(<SettingsPage />);

    fireEvent.change(screen.getByLabelText("Database label"), {
      target: { value: "Renamed Database" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Invalid timezone."));
  });

  it("disables the Save button when the database label is blank", () => {
    mockSettingsHook();
    mockTimezonesHook();
    mockCategoriesHook();

    render(<SettingsPage />);

    fireEvent.change(screen.getByLabelText("Database label"), { target: { value: "   " } });

    expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled();
  });

  it("renders timezone options with their UTC offsets and preselects the saved zone", () => {
    mockSettingsHook();
    mockTimezonesHook();
    mockCategoriesHook();

    render(<SettingsPage />);

    const select = screen.getByLabelText("Timezone");
    expect(select).toHaveValue("Europe/Lisbon");
    expect(within(select).getByRole("option", { name: "Europe/Lisbon (UTC+01:00)" })).toBeInTheDocument();
    expect(within(select).getByRole("option", { name: "America/New_York (UTC-04:00)" })).toBeInTheDocument();
  });

  it("PATCHes with the bare zone name when the timezone selection changes", async () => {
    const save = vi.fn().mockResolvedValue(undefined);
    mockSettingsHook({ save });
    mockTimezonesHook();
    mockCategoriesHook();

    render(<SettingsPage />);

    fireEvent.change(screen.getByLabelText("Timezone"), {
      target: { value: "Europe/Madrid" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Settings saved."));

    expect(save).toHaveBeenCalledWith({ timezone: "Europe/Madrid" });
  });

  it("keeps the currently saved zone selectable even if the timezone list fetch failed", () => {
    mockSettingsHook({ settings: makeSettings({ timezone: "Pacific/Auckland" }) });
    mockTimezonesHook({ timezones: [], loading: false, error: "Failed to load timezones." });
    mockCategoriesHook();

    render(<SettingsPage />);

    expect(screen.getByLabelText("Timezone")).toHaveValue("Pacific/Auckland");
    expect(screen.getByRole("button", { name: "Save changes" })).not.toBeDisabled();
  });

  it("lists existing categories as chips", () => {
    mockSettingsHook();
    mockTimezonesHook();
    mockCategoriesHook({ categories: [makeCategory({ id: 1, name: "Deep Work" })] });

    render(<SettingsPage />);

    expect(screen.getByText("Deep Work")).toBeInTheDocument();
  });

  it("creates a category and shows it in the list", async () => {
    const reload = vi.fn().mockResolvedValue(undefined);
    vi.mocked(createCategory).mockResolvedValue(makeCategory({ id: 2, name: "Errands" }));
    mockSettingsHook();
    mockTimezonesHook();
    mockCategoriesHook({ reload });

    render(<SettingsPage />);

    fireEvent.change(screen.getByLabelText("Category name"), { target: { value: "Errands" } });
    fireEvent.click(screen.getByRole("button", { name: "Add category" }));

    await waitFor(() => expect(createCategory).toHaveBeenCalled());

    expect(createCategory).toHaveBeenCalledWith({
      name: "Errands",
      color: "blue",
      sort_order: 0,
    });
    expect(reload).toHaveBeenCalled();
    await waitFor(() => expect(screen.getByLabelText("Category name")).toHaveValue(""));
  });

  it("shows a duplicate-name message on a 409 conflict", async () => {
    vi.mocked(createCategory).mockRejectedValue(new ApiError(409, "conflict", "Category already exists."));
    mockSettingsHook();
    mockTimezonesHook();
    mockCategoriesHook();

    render(<SettingsPage />);

    fireEvent.change(screen.getByLabelText("Category name"), { target: { value: "Deep Work" } });
    fireEvent.click(screen.getByRole("button", { name: "Add category" }));

    await waitFor(() =>
      expect(screen.getByText('A category named "Deep Work" already exists.')).toBeInTheDocument(),
    );
  });

  it("rejects a blank category name", () => {
    mockSettingsHook();
    mockTimezonesHook();
    mockCategoriesHook();

    render(<SettingsPage />);

    fireEvent.change(screen.getByLabelText("Category name"), { target: { value: "   " } });

    expect(screen.getByRole("button", { name: "Add category" })).toBeDisabled();
    expect(createCategory).not.toHaveBeenCalled();
  });
});
