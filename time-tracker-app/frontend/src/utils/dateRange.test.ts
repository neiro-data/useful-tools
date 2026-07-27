import { describe, expect, it } from "vitest";
import { formatCalendarWeek, formatCalendarWeekOfIsoDate, isoWeekNumber } from "./dateRange";

/** Local-midnight `Date` for a `YYYY-MM-DD` string, matching how the app builds dates everywhere
 * else (`new Date("2026-12-31")` would parse as UTC and can land on the previous local day). */
function localDate(isoDate: string): Date {
  return new Date(`${isoDate}T00:00:00`);
}

describe("isoWeekNumber", () => {
  it("numbers a mid-year week", () => {
    // Mon 2026-07-27 .. Sun 2026-08-02 is ISO week 31.
    expect(isoWeekNumber(localDate("2026-07-27"))).toBe(31);
    expect(isoWeekNumber(localDate("2026-08-02"))).toBe(31);
  });

  // The year-boundary cases are the whole reason this is Thursday-anchored rather than a simple
  // "days since Jan 1 / 7". A naive implementation gets every one of these wrong.
  it("rolls late-December days into week 1 of the NEXT ISO year", () => {
    // Mon 2024-12-30's week contains Thu 2025-01-02, so it belongs to 2025 — week 1, not 53.
    expect(isoWeekNumber(localDate("2024-12-30"))).toBe(1);
    expect(isoWeekNumber(localDate("2024-12-31"))).toBe(1);
  });

  it("rolls early-January days back into the LAST week of the previous ISO year", () => {
    // Sun 2023-01-01's week starts Mon 2022-12-26 and contains Thu 2022-12-29 -> 2022's week 52.
    expect(isoWeekNumber(localDate("2023-01-01"))).toBe(52);
    // Fri 2027-01-01's week contains Thu 2026-12-31 -> 2026's week 53 (see below).
    expect(isoWeekNumber(localDate("2027-01-01"))).toBe(53);
  });

  it("returns 53 in a 53-week ISO year", () => {
    // 2026 starts on a Thursday, which is exactly the condition for a 53-week ISO year.
    expect(isoWeekNumber(localDate("2026-12-28"))).toBe(53);
    expect(isoWeekNumber(localDate("2026-12-31"))).toBe(53);
    // ...and the very next Monday restarts the count.
    expect(isoWeekNumber(localDate("2027-01-04"))).toBe(1);
  });

  it("gives every day of one ISO week the same number, across a month boundary", () => {
    // Mon 2026-06-29 .. Sun 2026-07-05 spans June into July but is a single ISO week.
    const week = ["06-29", "06-30", "07-01", "07-02", "07-03", "07-04", "07-05"];
    const numbers = week.map((suffix) => isoWeekNumber(localDate(`2026-${suffix}`)));
    expect(new Set(numbers)).toEqual(new Set([27]));
  });

  it("is unaffected by a DST transition inside the week", () => {
    // EU clocks go forward on the last Sunday of March (2026-03-29). The week Mon 2026-03-23 ..
    // Sun 2026-03-29 is one hour short, which is what the Math.round in the implementation absorbs.
    expect(isoWeekNumber(localDate("2026-03-23"))).toBe(13);
    expect(isoWeekNumber(localDate("2026-03-29"))).toBe(13);
  });
});

describe("formatCalendarWeek", () => {
  it("zero-pads single-digit weeks", () => {
    // Explicitly requested: week 1 must read "CW 01", not "CW 1".
    expect(formatCalendarWeek(localDate("2026-01-01"))).toBe("CW 01");
    expect(formatCalendarWeek(localDate("2026-02-23"))).toBe("CW 09");
  });

  it("leaves two-digit weeks unpadded", () => {
    expect(formatCalendarWeek(localDate("2026-07-27"))).toBe("CW 31");
    expect(formatCalendarWeek(localDate("2026-12-28"))).toBe("CW 53");
  });

  it("formats from an ISO date string identically", () => {
    expect(formatCalendarWeekOfIsoDate("2026-07-27")).toBe("CW 31");
    expect(formatCalendarWeekOfIsoDate("2026-01-01")).toBe("CW 01");
  });
});
