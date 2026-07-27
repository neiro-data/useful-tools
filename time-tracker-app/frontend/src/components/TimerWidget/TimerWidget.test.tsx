import { render, screen, fireEvent, act } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TimerWidget } from "./TimerWidget";
import type { CategoryRead, EntryRead, TagRead } from "../../api/types";

const noop = vi.fn();

const deepWork: CategoryRead = { id: 1, name: "Deep Work", color: "blue", is_active: true, sort_order: 0 };

describe("TimerWidget", () => {
  it("renders the idle quick-add form when no timer is running", () => {
    render(
      <TimerWidget
        runningEntry={null}
        categories={[]}
        knownTags={[]}
        recentCategories={[]}
        recentTags={[]}
        onStart={noop}
        onStop={noop}
        onUpdateRunning={noop}
        onManualAdd={noop}
      />,
    );

    expect(screen.getByPlaceholderText("What are you working on?")).toBeInTheDocument();
    expect(screen.getByText("Start ▶")).toBeInTheDocument();
    expect(screen.getByText("Start ▶")).toBeDisabled();
  });

  it("keeps Start disabled with a title but no category, and shows a hint", () => {
    render(
      <TimerWidget
        runningEntry={null}
        categories={[deepWork]}
        knownTags={[]}
        recentCategories={[]}
        recentTags={[]}
        onStart={noop}
        onStop={noop}
        onUpdateRunning={noop}
        onManualAdd={noop}
      />,
    );

    const input = screen.getByPlaceholderText("What are you working on?");
    fireEvent.change(input, { target: { value: "Deep focus block" } });

    expect(screen.getByText("Start ▶")).toBeDisabled();
    expect(screen.getByText("Pick a category to start.")).toBeInTheDocument();
  });

  it("enables Start once a title and category are picked and calls onStart", () => {
    const onStart = vi.fn();
    render(
      <TimerWidget
        runningEntry={null}
        categories={[deepWork]}
        knownTags={[]}
        recentCategories={[deepWork]}
        recentTags={[]}
        onStart={onStart}
        onStop={noop}
        onUpdateRunning={noop}
        onManualAdd={noop}
      />,
    );

    const input = screen.getByPlaceholderText("What are you working on?");
    fireEvent.change(input, { target: { value: "Deep focus block" } });
    // Recent-category chip picks the category (avoids reaching into the portalled popover).
    fireEvent.click(screen.getByText("Deep Work"));

    const startButton = screen.getByText("Start ▶");
    expect(startButton).toBeEnabled();
    fireEvent.click(startButton);

    expect(onStart).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Deep focus block", category: deepWork, tagNames: [], notes: null }),
    );
  });

  it("passes a typed comment through to the start payload", () => {
    const onStart = vi.fn();
    render(
      <TimerWidget
        runningEntry={null}
        categories={[deepWork]}
        knownTags={[]}
        recentCategories={[deepWork]}
        recentTags={[]}
        onStart={onStart}
        onStop={noop}
        onUpdateRunning={noop}
        onManualAdd={noop}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText("What are you working on?"), {
      target: { value: "Deep focus block" },
    });
    fireEvent.click(screen.getByText("Deep Work"));
    fireEvent.change(screen.getByLabelText("Quick-add comment"), {
      target: { value: "Follow up with team" },
    });
    fireEvent.click(screen.getByText("Start ▶"));

    expect(onStart).toHaveBeenCalledWith(expect.objectContaining({ notes: "Follow up with team" }));
  });

  it("picks a recent category via the 1-6 shortcut when focus is outside a field", () => {
    const onStart = vi.fn();
    const { container } = render(
      <TimerWidget
        runningEntry={null}
        categories={[deepWork]}
        knownTags={[]}
        recentCategories={[deepWork]}
        recentTags={[]}
        onStart={onStart}
        onStop={noop}
        onUpdateRunning={noop}
        onManualAdd={noop}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText("What are you working on?"), {
      target: { value: "Deep focus block" },
    });
    // Move focus off the title input before dispatching the shortcut, so it lands on the card
    // root rather than a field.
    const root = container.querySelector('[data-mode="idle"]') as HTMLElement;
    root.focus();
    fireEvent.keyDown(root, { key: "1" });

    fireEvent.click(screen.getByText("Start ▶"));

    expect(onStart).toHaveBeenCalledWith(expect.objectContaining({ category: deepWork }));
  });

  it("allows typing '1' into the quick-add title input instead of triggering the shortcut", () => {
    const onStart = vi.fn();
    render(
      <TimerWidget
        runningEntry={null}
        categories={[deepWork]}
        knownTags={[]}
        recentCategories={[deepWork]}
        recentTags={[]}
        onStart={onStart}
        onStop={noop}
        onUpdateRunning={noop}
        onManualAdd={noop}
      />,
    );

    const input = screen.getByPlaceholderText("What are you working on?");
    fireEvent.keyDown(input, { key: "1" });
    fireEvent.change(input, { target: { value: "1" } });

    // The shortcut must not have fired: no category got auto-selected, so Start stays disabled.
    expect(input).toHaveValue("1");
    expect(screen.getByText("Start ▶")).toBeDisabled();
  });

  it("picks a recent tag via the Shift+1-6 shortcut when focus is outside a field", () => {
    const onStart = vi.fn();
    const bug: TagRead = { id: 1, name: "bug", is_active: true };
    const { container } = render(
      <TimerWidget
        runningEntry={null}
        categories={[deepWork]}
        knownTags={[bug]}
        recentCategories={[deepWork]}
        recentTags={[bug]}
        onStart={onStart}
        onStop={noop}
        onUpdateRunning={noop}
        onManualAdd={noop}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText("What are you working on?"), {
      target: { value: "Deep focus block" },
    });
    fireEvent.click(screen.getByText("Deep Work"));

    const root = container.querySelector('[data-mode="idle"]') as HTMLElement;
    root.focus();
    fireEvent.keyDown(root, { key: "1", shiftKey: true });

    fireEvent.click(screen.getByText("Start ▶"));

    expect(onStart).toHaveBeenCalledWith(expect.objectContaining({ tagNames: ["bug"] }));
  });

  it("allows typing '1' into the manual-mode date/time fields instead of triggering shortcuts", () => {
    const onStart = vi.fn();
    render(
      <TimerWidget
        runningEntry={null}
        categories={[deepWork]}
        knownTags={[]}
        recentCategories={[deepWork]}
        recentTags={[]}
        onStart={onStart}
        onStop={noop}
        onUpdateRunning={noop}
        onManualAdd={noop}
      />,
    );

    fireEvent.click(screen.getByText("+ Manual entry"));

    const hourSelect = screen.getByLabelText("Start hour");
    fireEvent.keyDown(hourSelect, { key: "1" });

    // The shortcut must not have fired: no category got auto-selected from the recent chip.
    expect(screen.getByText("Save")).toBeDisabled();
  });

  it("submits the correct ISO start/end timestamps built from the manual date/hour/minute pickers", () => {
    const onManualAdd = vi.fn();
    render(
      <TimerWidget
        runningEntry={null}
        categories={[deepWork]}
        knownTags={[]}
        recentCategories={[deepWork]}
        recentTags={[]}
        onStart={noop}
        onStop={noop}
        onUpdateRunning={noop}
        onManualAdd={onManualAdd}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText("What are you working on?"), {
      target: { value: "Deep focus block" },
    });
    fireEvent.click(screen.getByText("Deep Work"));
    fireEvent.click(screen.getByText("+ Manual entry"));

    fireEvent.change(screen.getByLabelText("Start date"), { target: { value: "2026-07-13" } });
    fireEvent.change(screen.getByLabelText("Start hour"), { target: { value: "09" } });
    fireEvent.change(screen.getByLabelText("Start minute"), { target: { value: "30" } });
    fireEvent.change(screen.getByLabelText("End date"), { target: { value: "2026-07-13" } });
    fireEvent.change(screen.getByLabelText("End hour"), { target: { value: "10" } });
    fireEvent.change(screen.getByLabelText("End minute"), { target: { value: "00" } });

    fireEvent.click(screen.getByText("Save"));

    expect(onManualAdd).toHaveBeenCalledWith(
      expect.objectContaining({
        startTs: new Date("2026-07-13T09:30").toISOString(),
        endTs: new Date("2026-07-13T10:00").toISOString(),
      }),
    );
  });

  it("renders the running state with live timer and Stop button", () => {
    const runningEntry: EntryRead = {
      id: 1,
      title: "Writing quarterly report",
      notes: null,
      category: deepWork,
      tags: [],
      start_ts: new Date(Date.now() - 5000).toISOString(),
      end_ts: null,
      duration_minutes: null,
      entry_mode: "timer",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    render(
      <TimerWidget
        runningEntry={runningEntry}
        categories={[deepWork]}
        knownTags={[]}
        recentCategories={[]}
        recentTags={[]}
        onStart={noop}
        onStop={noop}
        onUpdateRunning={noop}
        onManualAdd={noop}
      />,
    );

    expect(screen.getByText("Tracking")).toBeInTheDocument();
    expect(screen.getByText("Stop ⏹")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Writing quarterly report")).toBeInTheDocument();
  });

  it("does not trim the running-timer comment while typing", () => {
    // Regression guard: this input is controlled by `runningEntry.notes`, i.e. the value that
    // comes back from the server on every keystroke. Trimming per-keystroke would eat a trailing
    // space the instant it is typed, making multi-word comments impossible to enter.
    const onUpdateRunning = vi.fn();
    const runningEntry: EntryRead = {
      id: 1,
      title: "Writing quarterly report",
      notes: "draft",
      category: deepWork,
      tags: [],
      start_ts: new Date(Date.now() - 5000).toISOString(),
      end_ts: null,
      duration_minutes: null,
      entry_mode: "timer",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    render(
      <TimerWidget
        runningEntry={runningEntry}
        categories={[deepWork]}
        knownTags={[]}
        recentCategories={[]}
        recentTags={[]}
        onStart={noop}
        onStop={noop}
        onUpdateRunning={onUpdateRunning}
        onManualAdd={noop}
      />,
    );

    fireEvent.change(screen.getByLabelText("Running entry comment"), {
      target: { value: "draft " },
    });

    expect(onUpdateRunning).toHaveBeenCalledWith(expect.objectContaining({ notes: "draft " }));
  });

  it("sends null rather than an empty string when the running comment is cleared", () => {
    const onUpdateRunning = vi.fn();
    const runningEntry: EntryRead = {
      id: 1,
      title: "Writing quarterly report",
      notes: "draft",
      category: deepWork,
      tags: [],
      start_ts: new Date(Date.now() - 5000).toISOString(),
      end_ts: null,
      duration_minutes: null,
      entry_mode: "timer",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    render(
      <TimerWidget
        runningEntry={runningEntry}
        categories={[deepWork]}
        knownTags={[]}
        recentCategories={[]}
        recentTags={[]}
        onStart={noop}
        onStop={noop}
        onUpdateRunning={onUpdateRunning}
        onManualAdd={noop}
      />,
    );

    fireEvent.change(screen.getByLabelText("Running entry comment"), { target: { value: "" } });

    expect(onUpdateRunning).toHaveBeenCalledWith(expect.objectContaining({ notes: null }));
  });

  it("clears the tag chips and TagEditor's draft text after a successful Start", async () => {
    const bug: TagRead = { id: 1, name: "bug", is_active: true };
    const onStart = vi.fn();
    render(
      <TimerWidget
        runningEntry={null}
        categories={[deepWork]}
        knownTags={[bug]}
        recentCategories={[deepWork]}
        recentTags={[]}
        onStart={onStart}
        onStop={noop}
        onUpdateRunning={noop}
        onManualAdd={noop}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText("What are you working on?"), {
      target: { value: "Deep focus block" },
    });
    fireEvent.click(screen.getByText("Deep Work"));
    fireEvent.change(screen.getByLabelText("Add tag"), { target: { value: "bug" } });
    fireEvent.keyDown(screen.getByLabelText("Add tag"), { key: "Enter" });
    // Leave an uncommitted draft too.
    fireEvent.change(screen.getByLabelText("Add tag"), { target: { value: "urg" } });

    await act(async () => {
      fireEvent.click(screen.getByText("Start ▶"));
      await Promise.resolve();
    });

    expect(onStart).toHaveBeenCalledWith(expect.objectContaining({ tagNames: ["bug"] }));
    expect(screen.queryByText("#bug")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Add tag")).toHaveValue("");
  });

  it("clears the tag chips and TagEditor's draft text after a successful manual save", async () => {
    const bug: TagRead = { id: 1, name: "bug", is_active: true };
    const onManualAdd = vi.fn();
    render(
      <TimerWidget
        runningEntry={null}
        categories={[deepWork]}
        knownTags={[bug]}
        recentCategories={[deepWork]}
        recentTags={[]}
        onStart={noop}
        onStop={noop}
        onUpdateRunning={noop}
        onManualAdd={onManualAdd}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText("What are you working on?"), {
      target: { value: "Deep focus block" },
    });
    fireEvent.click(screen.getByText("Deep Work"));
    fireEvent.click(screen.getByText("+ Manual entry"));
    fireEvent.change(screen.getByLabelText("Add tag"), { target: { value: "bug" } });
    fireEvent.keyDown(screen.getByLabelText("Add tag"), { key: "Enter" });
    fireEvent.change(screen.getByLabelText("Add tag"), { target: { value: "urg" } });

    await act(async () => {
      fireEvent.click(screen.getByText("Save"));
      await Promise.resolve();
    });

    expect(onManualAdd).toHaveBeenCalledWith(expect.objectContaining({ tagNames: ["bug"] }));
    expect(screen.queryByText("#bug")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Add tag")).toHaveValue("");
  });
});
