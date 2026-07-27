import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TagEditor } from "./TagEditor";
import type { TagRead } from "../../api/types";

const focus: TagRead = { id: 1, name: "focus", is_active: true };
const urgent: TagRead = { id: 2, name: "urgent", is_active: true };
const bug: TagRead = { id: 3, name: "bug", is_active: true };
const knownTags = [focus, urgent, bug];

describe("TagEditor", () => {
  it("commits a chip on Enter and clears the draft", () => {
    const onChange = vi.fn();
    render(<TagEditor value={[]} onChange={onChange} />);

    fireEvent.change(screen.getByLabelText("Add tag"), { target: { value: "focus" } });
    fireEvent.keyDown(screen.getByLabelText("Add tag"), { key: "Enter" });

    expect(onChange).toHaveBeenCalledWith(["focus"]);
  });

  it("commits a chip on ','", () => {
    const onChange = vi.fn();
    render(<TagEditor value={[]} onChange={onChange} />);

    fireEvent.change(screen.getByLabelText("Add tag"), { target: { value: "focus" } });
    fireEvent.keyDown(screen.getByLabelText("Add tag"), { key: "," });

    expect(onChange).toHaveBeenCalledWith(["focus"]);
  });

  it("removes the last chip on Backspace with an empty draft", () => {
    const onChange = vi.fn();
    render(<TagEditor value={["focus", "urgent"]} onChange={onChange} />);

    fireEvent.keyDown(screen.getByLabelText("Add tag"), { key: "Backspace" });

    expect(onChange).toHaveBeenCalledWith(["focus"]);
  });

  it("degrades to filter-only suggestions (no Recent section) when recentTags is omitted", () => {
    render(<TagEditor value={[]} onChange={vi.fn()} knownTags={knownTags} />);

    fireEvent.focus(screen.getByLabelText("Add tag"));

    expect(screen.queryByText("Recent")).not.toBeInTheDocument();
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("shows a 'Recent' section on focus with an empty draft when recentTags is provided", () => {
    render(<TagEditor value={[]} onChange={vi.fn()} knownTags={knownTags} recentTags={[urgent, focus]} />);

    fireEvent.focus(screen.getByLabelText("Add tag"));

    expect(screen.getByText("Recent")).toBeInTheDocument();
    expect(screen.getByText("#urgent")).toBeInTheDocument();
    expect(screen.getByText("#focus")).toBeInTheDocument();
  });

  it("excludes already-applied tags from the Recent section", () => {
    render(
      <TagEditor value={["focus"]} onChange={vi.fn()} knownTags={knownTags} recentTags={[urgent, focus]} />,
    );

    fireEvent.focus(screen.getByLabelText("Add tag"));

    expect(screen.queryByText("#focus", { selector: "button" })).not.toBeInTheDocument();
    expect(screen.getByText("#urgent")).toBeInTheDocument();
  });

  it("caps the Recent section at 8 tags", () => {
    const many: TagRead[] = Array.from({ length: 12 }, (_, index) => ({
      id: 100 + index,
      name: `tag${index}`,
      is_active: true,
    }));
    render(<TagEditor value={[]} onChange={vi.fn()} knownTags={many} recentTags={many} />);

    fireEvent.focus(screen.getByLabelText("Add tag"));

    expect(screen.getAllByRole("option")).toHaveLength(8);
  });

  it("switches from Recent to filtered suggestions once the user starts typing", () => {
    render(<TagEditor value={[]} onChange={vi.fn()} knownTags={knownTags} recentTags={[urgent]} />);

    const input = screen.getByLabelText("Add tag");
    fireEvent.focus(input);
    expect(screen.getByText("Recent")).toBeInTheDocument();

    fireEvent.change(input, { target: { value: "foc" } });

    expect(screen.queryByText("Recent")).not.toBeInTheDocument();
    expect(screen.getByText("#focus")).toBeInTheDocument();
  });

  it("opens the full known-tag dropdown via the ▾ toggle, alphabetically ordered", () => {
    render(<TagEditor value={[]} onChange={vi.fn()} knownTags={knownTags} />);

    fireEvent.click(screen.getByLabelText("Show all tags"));

    const options = screen.getAllByRole("option").map((el) => el.textContent);
    expect(options).toEqual(["#bug", "#focus", "#urgent"]);
  });

  it("closes the dropdown on selecting an option", () => {
    const onChange = vi.fn();
    render(<TagEditor value={[]} onChange={onChange} knownTags={knownTags} />);

    fireEvent.click(screen.getByLabelText("Show all tags"));
    fireEvent.click(screen.getByText("#bug"));

    expect(onChange).toHaveBeenCalledWith(["bug"]);
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("closes the dropdown on Escape", () => {
    render(<TagEditor value={[]} onChange={vi.fn()} knownTags={knownTags} />);

    fireEvent.click(screen.getByLabelText("Show all tags"));
    expect(screen.getByRole("listbox")).toBeInTheDocument();

    fireEvent.keyDown(screen.getByLabelText("Add tag"), { key: "Escape" });

    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("closes the dropdown on an outside click", () => {
    render(
      <div>
        <TagEditor value={[]} onChange={vi.fn()} knownTags={knownTags} />
        <button type="button">outside</button>
      </div>,
    );

    fireEvent.click(screen.getByLabelText("Show all tags"));
    expect(screen.getByRole("listbox")).toBeInTheDocument();

    fireEvent.mouseDown(screen.getByText("outside"));

    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("navigates the open list with ArrowDown/Enter", () => {
    const onChange = vi.fn();
    render(<TagEditor value={[]} onChange={onChange} knownTags={knownTags} />);

    fireEvent.click(screen.getByLabelText("Show all tags"));
    const input = screen.getByLabelText("Add tag");
    fireEvent.keyDown(input, { key: "ArrowDown" }); // #bug
    fireEvent.keyDown(input, { key: "ArrowDown" }); // #focus
    fireEvent.keyDown(input, { key: "Enter" });

    expect(onChange).toHaveBeenCalledWith(["focus"]);
  });
});
