import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TimerWidget } from "./TimerWidget";
import type { CategoryRead, EntryRead } from "../../api/types";

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
});
