import { render, screen, fireEvent } from "@testing-library/react";
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
});
