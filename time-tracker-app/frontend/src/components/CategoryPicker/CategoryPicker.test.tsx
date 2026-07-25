import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CategoryPicker } from "./CategoryPicker";
import type { CategoryRead } from "../../api/types";

function makeCategories(): CategoryRead[] {
  return [
    { id: 1, name: "Deep Work", color: "blue", is_active: true, sort_order: 0 },
    { id: 2, name: "Admin", color: "#e3db38", is_active: true, sort_order: 1 },
  ];
}

describe("CategoryPicker", () => {
  it("opens the popover and fires onChange with the selected category", () => {
    const onChange = vi.fn();
    render(<CategoryPicker categories={makeCategories()} value={null} onChange={onChange} />);

    fireEvent.click(screen.getByLabelText("Category"));
    expect(screen.getByRole("listbox")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Admin"));

    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ id: 2, name: "Admin" }));
  });

  it("fires onChange(null) when selecting 'No category'", () => {
    const onChange = vi.fn();
    const [firstCategory] = makeCategories();
    render(
      <CategoryPicker categories={makeCategories()} value={firstCategory ?? null} onChange={onChange} />,
    );

    fireEvent.click(screen.getByLabelText("Category"));
    fireEvent.click(screen.getByText("No category"));

    expect(onChange).toHaveBeenCalledWith(null);
  });

  it("stays open on mousedown inside the portalled popover", () => {
    // Regression guard: the popover is portalled to document.body, so it is NOT inside `rootRef`.
    // An outside-click handler that only checks `rootRef.contains(target)` would close the
    // popover on its own mousedown, making every option unclickable.
    render(<CategoryPicker categories={makeCategories()} value={null} onChange={vi.fn()} />);

    fireEvent.click(screen.getByLabelText("Category"));
    fireEvent.mouseDown(screen.getByText("Admin"));

    expect(screen.queryByRole("listbox")).toBeInTheDocument();
  });

  it("closes the popover on mousedown outside it", () => {
    render(<CategoryPicker categories={makeCategories()} value={null} onChange={vi.fn()} />);

    fireEvent.click(screen.getByLabelText("Category"));
    fireEvent.mouseDown(document.body);

    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("closes the popover on Escape", () => {
    render(<CategoryPicker categories={makeCategories()} value={null} onChange={vi.fn()} />);

    fireEvent.click(screen.getByLabelText("Category"));
    expect(screen.getByRole("listbox")).toBeInTheDocument();

    fireEvent.keyDown(document, { key: "Escape" });

    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });
});
