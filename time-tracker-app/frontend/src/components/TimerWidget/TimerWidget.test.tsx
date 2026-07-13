import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TimerWidget } from "./TimerWidget";
import type { EntryRead } from "../../api/types";

const noop = vi.fn();

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

  it("enables Start once a title is typed and calls onStart", () => {
    const onStart = vi.fn();
    render(
      <TimerWidget
        runningEntry={null}
        categories={[]}
        knownTags={[]}
        recentCategories={[]}
        recentTags={[]}
        onStart={onStart}
        onStop={noop}
        onUpdateRunning={noop}
        onManualAdd={noop}
      />,
    );

    const input = screen.getByPlaceholderText("What are you working on?");
    fireEvent.change(input, { target: { value: "Deep focus block" } });
    const startButton = screen.getByText("Start ▶");
    expect(startButton).toBeEnabled();
    fireEvent.click(startButton);

    expect(onStart).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Deep focus block", tagNames: [] }),
    );
  });

  it("renders the running state with live timer and Stop button", () => {
    const runningEntry: EntryRead = {
      id: 1,
      title: "Writing quarterly report",
      notes: null,
      category: null,
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

    expect(screen.getByText("Tracking")).toBeInTheDocument();
    expect(screen.getByText("Stop ⏹")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Writing quarterly report")).toBeInTheDocument();
  });
});
