import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DateTimePicker } from "./DateTimePicker";

describe("DateTimePicker", () => {
  it("splits the value into date/hour/minute controls", () => {
    render(<DateTimePicker value="2026-07-13T09:05" onChange={vi.fn()} label="Start" />);

    expect(screen.getByLabelText("Start date")).toHaveValue("2026-07-13");
    expect(screen.getByLabelText("Start hour")).toHaveValue("09");
    expect(screen.getByLabelText("Start minute")).toHaveValue("05");
  });

  it("emits the recombined YYYY-MM-DDTHH:mm value when the hour changes", () => {
    const onChange = vi.fn();
    render(<DateTimePicker value="2026-07-13T09:05" onChange={onChange} label="Start" />);

    fireEvent.change(screen.getByLabelText("Start hour"), { target: { value: "14" } });

    expect(onChange).toHaveBeenCalledWith("2026-07-13T14:05");
  });

  it("emits the recombined value when the minute changes", () => {
    const onChange = vi.fn();
    render(<DateTimePicker value="2026-07-13T09:05" onChange={onChange} label="Start" />);

    fireEvent.change(screen.getByLabelText("Start minute"), { target: { value: "30" } });

    expect(onChange).toHaveBeenCalledWith("2026-07-13T09:30");
  });

  it("emits the recombined value when the date changes", () => {
    const onChange = vi.fn();
    render(<DateTimePicker value="2026-07-13T09:05" onChange={onChange} label="Start" />);

    fireEvent.change(screen.getByLabelText("Start date"), { target: { value: "2026-08-01" } });

    expect(onChange).toHaveBeenCalledWith("2026-08-01T09:05");
  });

  it("only offers 00-23 hour options and 00-59 minute options", () => {
    render(<DateTimePicker value="2026-07-13T09:05" onChange={vi.fn()} label="Start" />);

    const hourOptions = screen
      .getAllByRole<HTMLOptionElement>("option", { name: /^\d{2}$/ })
      .filter((option) => option.closest("select") === screen.getByLabelText("Start hour"))
      .map((option) => option.value);
    expect(hourOptions).toEqual(Array.from({ length: 24 }, (_, h) => h.toString().padStart(2, "0")));

    const minuteOptions = screen
      .getAllByRole<HTMLOptionElement>("option")
      .filter((option) => option.closest("select") === screen.getByLabelText("Start minute"))
      .map((option) => option.value);
    expect(minuteOptions).toEqual(Array.from({ length: 60 }, (_, m) => m.toString().padStart(2, "0")));
  });

  it("keeps any in-range minute selectable", () => {
    render(<DateTimePicker value="2026-07-13T09:37" onChange={vi.fn()} label="Start" />);

    expect(screen.getByLabelText("Start minute")).toHaveValue("37");
  });

  it("falls back to 00 for an out-of-range minute instead of injecting it", () => {
    render(<DateTimePicker value="2026-07-13T09:61" onChange={vi.fn()} label="Start" />);

    expect(screen.getByLabelText("Start minute")).toHaveValue("00");

    const minuteOptions = screen
      .getAllByRole<HTMLOptionElement>("option")
      .filter((option) => option.closest("select") === screen.getByLabelText("Start minute"))
      .map((option) => option.value);
    expect(minuteOptions).not.toContain("61");
  });

  it("falls back to 00 for an out-of-range hour instead of injecting it", () => {
    render(<DateTimePicker value="2026-07-13T99:05" onChange={vi.fn()} label="Start" />);

    expect(screen.getByLabelText("Start hour")).toHaveValue("00");
  });

  it("falls back gracefully on a malformed or empty value", () => {
    render(<DateTimePicker value="" onChange={vi.fn()} label="Start" />);

    expect(screen.getByLabelText("Start hour")).toHaveValue("00");
    expect(screen.getByLabelText("Start minute")).toHaveValue("00");
  });

  it("falls back gracefully on garbage input instead of throwing", () => {
    expect(() =>
      render(<DateTimePicker value="not-a-date" onChange={vi.fn()} label="Start" />),
    ).not.toThrow();

    expect(screen.getByLabelText("Start hour")).toHaveValue("00");
    expect(screen.getByLabelText("Start minute")).toHaveValue("00");
  });

  it("emits a value matching the YYYY-MM-DDTHH:mm wire format", () => {
    const onChange = vi.fn();
    render(<DateTimePicker value="2026-07-13T09:05" onChange={onChange} label="Start" />);

    fireEvent.change(screen.getByLabelText("Start hour"), { target: { value: "14" } });

    expect(onChange).toHaveBeenCalledWith(expect.stringMatching(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/));
  });
});
