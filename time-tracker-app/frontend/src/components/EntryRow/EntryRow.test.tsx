import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { EntryRow } from "./EntryRow";
import type { EntryRead } from "../../api/types";

function makeEntry(overrides: Partial<EntryRead> = {}): EntryRead {
  return {
    id: 1,
    title: "Write quarterly report",
    notes: null,
    category: { id: 1, name: "Deep Work", color: "blue", is_active: true, sort_order: 0 },
    tags: [{ id: 1, name: "focus", is_active: true }],
    start_ts: "2026-07-13T09:00:00+00:00",
    end_ts: "2026-07-13T10:30:00+00:00",
    duration_minutes: 90,
    entry_mode: "manual",
    created_at: "2026-07-13T09:00:05+00:00",
    updated_at: "2026-07-13T10:30:02+00:00",
    ...overrides,
  };
}

describe("EntryRow", () => {
  it("renders title, category, tags and formatted duration in view mode", () => {
    render(
      <EntryRow entry={makeEntry()} categories={[]} knownTags={[]} onSave={vi.fn()} onDelete={vi.fn()} />,
    );

    expect(screen.getByText("Write quarterly report")).toBeInTheDocument();
    expect(screen.getByText("Deep Work")).toBeInTheDocument();
    expect(screen.getByText("#focus")).toBeInTheDocument();
    expect(screen.getByText("1h 30m")).toBeInTheDocument();
  });

  it("shows '…' for duration and skips category-color bar while running", () => {
    const entry = makeEntry({ end_ts: null, duration_minutes: null, entry_mode: "timer" });
    render(
      <EntryRow entry={entry} categories={[]} knownTags={[]} isRunning onSave={vi.fn()} onDelete={vi.fn()} />,
    );

    expect(screen.getByText("…")).toBeInTheDocument();
  });

  it("enters edit mode on row click and calls onSave with updated title", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(
      <EntryRow entry={makeEntry()} categories={[]} knownTags={[]} onSave={onSave} onDelete={vi.fn()} />,
    );

    fireEvent.click(screen.getByTestId("entry-row"));
    const titleInput = screen.getByLabelText("Entry title");
    fireEvent.change(titleInput, { target: { value: "Updated title" } });
    fireEvent.click(screen.getByText("Save"));

    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Updated title", tagNames: ["focus"] }),
    );
  });

  it("opens delete confirmation and calls onDelete on confirm", () => {
    const onDelete = vi.fn();
    render(
      <EntryRow entry={makeEntry()} categories={[]} knownTags={[]} onSave={vi.fn()} onDelete={onDelete} />,
    );

    fireEvent.click(screen.getByLabelText("Actions for Write quarterly report"));
    fireEvent.click(screen.getByText("Yes, delete"));

    expect(onDelete).toHaveBeenCalled();
  });
});
