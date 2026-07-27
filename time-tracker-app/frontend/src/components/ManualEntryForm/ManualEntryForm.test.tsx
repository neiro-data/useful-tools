import { render, screen, fireEvent, act } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ManualEntryForm } from "./ManualEntryForm";
import type { CategoryRead } from "../../api/types";

const deepWork: CategoryRead = { id: 1, name: "Deep Work", color: "blue", is_active: true, sort_order: 0 };

describe("ManualEntryForm", () => {
  it("rejects submit with no category and shows an error", () => {
    const onSubmit = vi.fn();
    render(
      <ManualEntryForm
        categories={[deepWork]}
        knownTags={[]}
        defaultStart="2026-07-13T09:00"
        defaultEnd="2026-07-13T10:00"
        onSubmit={onSubmit}
        onCancel={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText("Manual entry title"), { target: { value: "Write docs" } });
    fireEvent.click(screen.getByText("Save"));

    expect(screen.getByRole("alert")).toHaveTextContent("Category is required.");
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits with the selected category and comment", () => {
    const onSubmit = vi.fn();
    render(
      <ManualEntryForm
        categories={[deepWork]}
        knownTags={[]}
        defaultStart="2026-07-13T09:00"
        defaultEnd="2026-07-13T10:00"
        onSubmit={onSubmit}
        onCancel={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText("Manual entry title"), { target: { value: "Write docs" } });
    fireEvent.click(screen.getByLabelText("Category *"));
    fireEvent.click(screen.getByText("Deep Work"));
    fireEvent.change(screen.getByLabelText("Manual entry comment"), {
      target: { value: "Draft only" },
    });
    fireEvent.click(screen.getByText("Save"));

    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ category_id: 1, notes: "Draft only" }));
  });

  it("builds the ISO start/end timestamps from the date/hour/minute pickers", () => {
    const onSubmit = vi.fn();
    render(
      <ManualEntryForm
        categories={[deepWork]}
        knownTags={[]}
        defaultStart="2026-07-13T09:00"
        defaultEnd="2026-07-13T10:00"
        onSubmit={onSubmit}
        onCancel={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText("Manual entry title"), { target: { value: "Write docs" } });
    fireEvent.click(screen.getByLabelText("Category *"));
    fireEvent.click(screen.getByText("Deep Work"));

    fireEvent.change(screen.getByLabelText("Start date"), { target: { value: "2026-07-13" } });
    fireEvent.change(screen.getByLabelText("Start hour"), { target: { value: "08" } });
    fireEvent.change(screen.getByLabelText("Start minute"), { target: { value: "15" } });
    fireEvent.change(screen.getByLabelText("End hour"), { target: { value: "09" } });
    fireEvent.change(screen.getByLabelText("End minute"), { target: { value: "45" } });

    fireEvent.click(screen.getByText("Save"));

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        start_ts: new Date("2026-07-13T08:15").toISOString(),
        end_ts: new Date("2026-07-13T09:45").toISOString(),
      }),
    );
  });

  it("rejects submit when the end time is before the start time", () => {
    const onSubmit = vi.fn();
    render(
      <ManualEntryForm
        categories={[deepWork]}
        knownTags={[]}
        defaultStart="2026-07-13T09:00"
        defaultEnd="2026-07-13T10:00"
        onSubmit={onSubmit}
        onCancel={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText("Manual entry title"), { target: { value: "Write docs" } });
    fireEvent.click(screen.getByLabelText("Category *"));
    fireEvent.click(screen.getByText("Deep Work"));

    fireEvent.change(screen.getByLabelText("End hour"), { target: { value: "08" } });

    // The error surfaces as soon as the pickers cross over — no Save click required — and Save is
    // disabled while it stands, so the entry can't be added at all.
    expect(screen.getByRole("alert")).toHaveTextContent("End must be on or after start.");
    expect(screen.getByText("Save")).toBeDisabled();

    fireEvent.click(screen.getByText("Save"));
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("clears the tag chips and TagEditor's draft text after a successful submit", async () => {
    const onSubmit = vi.fn();
    render(
      <ManualEntryForm
        categories={[deepWork]}
        knownTags={[]}
        defaultStart="2026-07-13T09:00"
        defaultEnd="2026-07-13T10:00"
        onSubmit={onSubmit}
        onCancel={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText("Manual entry title"), { target: { value: "Write docs" } });
    fireEvent.click(screen.getByLabelText("Category *"));
    fireEvent.click(screen.getByText("Deep Work"));
    fireEvent.change(screen.getByLabelText("Add tag"), { target: { value: "focus" } });
    fireEvent.keyDown(screen.getByLabelText("Add tag"), { key: "Enter" });
    // Leave an uncommitted draft too — TagEditor's own internal state, not just the chips.
    fireEvent.change(screen.getByLabelText("Add tag"), { target: { value: "urg" } });

    await act(async () => {
      fireEvent.click(screen.getByText("Save"));
      await Promise.resolve();
    });

    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ tagNames: ["focus"] }));
    expect(screen.queryByText("#focus", { selector: "span" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Add tag")).toHaveValue("");
  });

  it("preserves the form (chips and title) after a FAILED submit (validation error)", () => {
    const onSubmit = vi.fn();
    render(
      <ManualEntryForm
        categories={[deepWork]}
        knownTags={[]}
        defaultStart="2026-07-13T09:00"
        defaultEnd="2026-07-13T10:00"
        onSubmit={onSubmit}
        onCancel={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText("Manual entry title"), { target: { value: "Write docs" } });
    fireEvent.change(screen.getByLabelText("Add tag"), { target: { value: "focus" } });
    fireEvent.keyDown(screen.getByLabelText("Add tag"), { key: "Enter" });
    // No category picked -> submit fails validation before calling onSubmit.
    fireEvent.click(screen.getByText("Save"));

    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Manual entry title")).toHaveValue("Write docs");
    expect(screen.getByText("#focus")).toBeInTheDocument();
  });
});
