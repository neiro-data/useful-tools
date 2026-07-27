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
  it("labels a Monday-start week by its calendar week, with the date range in the title", () => {
    const bars = barsFromWeeks([
      { week_start: "2026-06-01", week_end: "2026-06-07", total_minutes: 120 },
    ]);

    expect(bars).toEqual([
      { key: "2026-06-01", label: "CW 23", title: "Jun 1–7", minutes: 120 },
    ]);
  });

  it("titles a week spanning a month boundary with both months", () => {
    const bars = barsFromWeeks([
      { week_start: "2026-06-29", week_end: "2026-07-05", total_minutes: 90 },
    ]);

    expect(bars).toEqual([
      { key: "2026-06-29", label: "CW 27", title: "Jun 29 – Jul 5", minutes: 90 },
    ]);
  });

  it("labels a single-day clipped week (start === end) by that day's calendar week", () => {
    const bars = barsFromWeeks([
      { week_start: "2026-06-01", week_end: "2026-06-01", total_minutes: 45 },
    ]);

    expect(bars).toEqual([
      { key: "2026-06-01", label: "CW 23", title: "Jun 1–1", minutes: 45 },
    ]);
  });

  it("labels a Sunday-start week by the ISO week its Monday–Saturday days belong to (off-by-one fix)", () => {
    // Sunday-start bucket: 2026-07-05 (Sun) .. 2026-07-11 (Sat). The Sunday itself is the last day
    // of ISO week 27, but Monday–Saturday (the other six days) are ISO week 28 — the bucket must
    // report CW 28, not CW 27.
    const bars = barsFromWeeks([
      { week_start: "2026-07-05", week_end: "2026-07-11", total_minutes: 60 },
    ]);

    expect(bars[0]).toMatchObject({ label: "CW 28" });
  });
});
