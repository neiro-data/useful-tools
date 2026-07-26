import { describe, expect, it } from "vitest";
import { barsFromDays, barsFromWeeks } from "./bars";

describe("barsFromDays", () => {
  it("labels a week-length range with weekday names", () => {
    const bars = barsFromDays([
      { isoDate: "2026-07-06", minutes: 30 }, // Monday
      { isoDate: "2026-07-07", minutes: 0 },
    ]);

    expect(bars).toEqual([
      { key: "2026-07-06", label: "Mon", minutes: 30 },
      { key: "2026-07-07", label: "Tue", minutes: 0 },
    ]);
  });

  it("switches to compact date labels for a range longer than a week", () => {
    const days = Array.from({ length: 8 }, (_, index) => ({
      isoDate: `2026-07-${String(index + 1).padStart(2, "0")}`,
      minutes: index,
    }));

    const bars = barsFromDays(days);

    expect(bars[0]).toMatchObject({ label: "Jul 1" });
    expect(bars[7]).toMatchObject({ label: "Jul 8" });
  });
});

describe("barsFromWeeks", () => {
  it("formats a week label compactly when it stays within one month", () => {
    const bars = barsFromWeeks([
      { week_start: "2026-06-01", week_end: "2026-06-07", total_minutes: 120 },
    ]);

    expect(bars).toEqual([{ key: "2026-06-01", label: "Jun 1–7", minutes: 120 }]);
  });

  it("formats a week label with both months when it spans a month boundary", () => {
    const bars = barsFromWeeks([
      { week_start: "2026-06-29", week_end: "2026-07-05", total_minutes: 90 },
    ]);

    expect(bars).toEqual([{ key: "2026-06-29", label: "Jun 29 – Jul 5", minutes: 90 }]);
  });

  it("formats a single-day clipped week (start === end)", () => {
    const bars = barsFromWeeks([
      { week_start: "2026-06-01", week_end: "2026-06-01", total_minutes: 45 },
    ]);

    expect(bars).toEqual([{ key: "2026-06-01", label: "Jun 1–1", minutes: 45 }]);
  });
});
