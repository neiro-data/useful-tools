import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { EntryRow } from "./EntryRow";
import { toLocalDateTimeInput } from "../../utils/timeRange";
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

  it("edits a saved entry's comment and forwards it to onSave", () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(
      <EntryRow entry={makeEntry()} categories={[]} knownTags={[]} onSave={onSave} onDelete={vi.fn()} />,
    );

    fireEvent.click(screen.getByTestId("entry-row"));
    fireEvent.change(screen.getByLabelText("Entry comment"), { target: { value: "Ping client" } });
    fireEvent.click(screen.getByText("Save"));

    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ notes: "Ping client" }));
  });

  it("prefills the start/end pickers with LOCAL wall time, not a UTC slice", () => {
    // Derives the expected local date/hour/minute via the same `toLocalDateTimeInput` the
    // component uses, so this assertion holds regardless of the runner's TZ — the point is that
    // it goes through local-time conversion, not a naive `toISOString().slice(0, 16)` (proven
    // TZ-sensitively in `utils/timeRange.test.ts`).
    const entry = makeEntry();
    const [expectedStartDate, expectedStartTime] = toLocalDateTimeInput(entry.start_ts).split("T");
    const [expectedEndDate, expectedEndTime] = toLocalDateTimeInput(entry.end_ts as string).split("T");
    const [expectedStartHour, expectedStartMinute] = expectedStartTime.split(":");
    const [expectedEndHour, expectedEndMinute] = expectedEndTime.split(":");

    render(<EntryRow entry={entry} categories={[]} knownTags={[]} onSave={vi.fn()} onDelete={vi.fn()} />);

    fireEvent.click(screen.getByTestId("entry-row"));

    expect(screen.getByLabelText("Start date")).toHaveValue(expectedStartDate);
    expect(screen.getByLabelText("Start hour")).toHaveValue(expectedStartHour);
    expect(screen.getByLabelText("Start minute")).toHaveValue(expectedStartMinute);
    expect(screen.getByLabelText("End date")).toHaveValue(expectedEndDate);
    expect(screen.getByLabelText("End hour")).toHaveValue(expectedEndHour);
    expect(screen.getByLabelText("End minute")).toHaveValue(expectedEndMinute);
  });

  it("submits ISO-UTC startTs/endTs derived from the edited pickers", () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(
      <EntryRow entry={makeEntry()} categories={[]} knownTags={[]} onSave={onSave} onDelete={vi.fn()} />,
    );

    fireEvent.click(screen.getByTestId("entry-row"));
    fireEvent.change(screen.getByLabelText("Start hour"), { target: { value: "08" } });
    fireEvent.change(screen.getByLabelText("Start minute"), { target: { value: "00" } });
    fireEvent.change(screen.getByLabelText("End hour"), { target: { value: "09" } });
    fireEvent.change(screen.getByLabelText("End minute"), { target: { value: "00" } });
    fireEvent.click(screen.getByText("Save"));

    const call = onSave.mock.calls[0]?.[0];
    // Both timestamps must be valid ISO-UTC strings ("Z" suffix), one hour apart (08:xx -> 09:xx
    // local, wherever "local" is for the runner).
    expect(call.startTs).toMatch(/Z$/);
    expect(call.endTs).toMatch(/Z$/);
    expect(new Date(call.endTs as string).getTime() - new Date(call.startTs as string).getTime()).toBe(
      60 * 60 * 1000,
    );
  });

  it("shows the range error and disables Save when end is set before start", () => {
    render(
      <EntryRow entry={makeEntry()} categories={[]} knownTags={[]} onSave={vi.fn()} onDelete={vi.fn()} />,
    );

    fireEvent.click(screen.getByTestId("entry-row"));
    // Move End's date a day before Start's — always "before", regardless of the runner's TZ.
    const startDate = (screen.getByLabelText("Start date") as HTMLInputElement).value;
    const dayBefore = new Date(`${startDate}T00:00`);
    dayBefore.setDate(dayBefore.getDate() - 1);
    fireEvent.change(screen.getByLabelText("End date"), {
      target: { value: dayBefore.toISOString().slice(0, 10) },
    });

    expect(screen.getByRole("alert")).toHaveTextContent("End must be on or after start.");
    expect(screen.getByText("Save")).toBeDisabled();
  });

  it("accepts an equal start and end (zero-length entry) and saves successfully", () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(
      <EntryRow entry={makeEntry()} categories={[]} knownTags={[]} onSave={onSave} onDelete={vi.fn()} />,
    );

    fireEvent.click(screen.getByTestId("entry-row"));
    // Set End to exactly match Start's current (local) hour/minute, whatever that is under the
    // runner's TZ.
    const startHour = (screen.getByLabelText("Start hour") as HTMLSelectElement).value;
    const startMinute = (screen.getByLabelText("Start minute") as HTMLSelectElement).value;
    fireEvent.change(screen.getByLabelText("End hour"), { target: { value: startHour } });
    fireEvent.change(screen.getByLabelText("End minute"), { target: { value: startMinute } });

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByText("Save")).toBeEnabled();
    fireEvent.click(screen.getByText("Save"));
    expect(onSave).toHaveBeenCalled();
  });

  it("replaces the End picker with a disabled 'Running…' affordance and skips the range check for a running entry", () => {
    const entry = makeEntry({ end_ts: null, duration_minutes: null, entry_mode: "timer" });
    render(
      <EntryRow entry={entry} categories={[]} knownTags={[]} isRunning onSave={vi.fn()} onDelete={vi.fn()} />,
    );

    fireEvent.click(screen.getByTestId("entry-row"));

    expect(screen.queryByLabelText("End date")).not.toBeInTheDocument();
    expect(screen.getByText("Running…")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByText("Save")).toBeEnabled();
  });

  it("CRITICAL: never sends endTs: null for a completed entry, and sends it only for a running one", () => {
    const onSaveCompleted = vi.fn().mockResolvedValue(undefined);
    const { unmount } = render(
      <EntryRow entry={makeEntry()} categories={[]} knownTags={[]} onSave={onSaveCompleted} onDelete={vi.fn()} />,
    );
    fireEvent.click(screen.getByTestId("entry-row"));
    fireEvent.click(screen.getByText("Save"));
    expect(onSaveCompleted).toHaveBeenCalledWith(
      expect.objectContaining({ endTs: expect.any(String) }),
    );
    expect(onSaveCompleted.mock.calls[0]?.[0].endTs).not.toBeNull();
    unmount();

    const onSaveRunning = vi.fn().mockResolvedValue(undefined);
    const runningEntry = makeEntry({ end_ts: null, duration_minutes: null, entry_mode: "timer" });
    render(
      <EntryRow
        entry={runningEntry}
        categories={[]}
        knownTags={[]}
        isRunning
        onSave={onSaveRunning}
        onDelete={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByTestId("entry-row"));
    fireEvent.click(screen.getByText("Save"));
    expect(onSaveRunning).toHaveBeenCalledWith(expect.objectContaining({ endTs: null }));
  });
});
