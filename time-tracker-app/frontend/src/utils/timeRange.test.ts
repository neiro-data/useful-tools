import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { timeRangeError, toLocalDateTimeInput } from "./timeRange";

describe("timeRangeError", () => {
  it("returns null when end is after start", () => {
    expect(timeRangeError("2026-07-13T09:00", "2026-07-13T10:00")).toBeNull();
  });

  it("allows end === start (zero-length entry)", () => {
    expect(timeRangeError("2026-07-13T09:00", "2026-07-13T09:00")).toBeNull();
  });

  it("rejects end before start", () => {
    expect(timeRangeError("2026-07-13T10:00", "2026-07-13T09:00")).toBe("End must be on or after start.");
  });

  it("returns a distinct message for unparseable input rather than treating it as valid", () => {
    expect(timeRangeError("not-a-date", "2026-07-13T09:00")).toBe(
      "Start and end must both be valid dates and times.",
    );
    expect(timeRangeError("2026-07-13T09:00", "also-not-a-date")).toBe(
      "Start and end must both be valid dates and times.",
    );
  });
});

describe("toLocalDateTimeInput", () => {
  const originalTz = process.env.TZ;

  beforeEach(() => {
    // A fixed non-UTC zone so the local-vs-UTC distinction actually bites: without it, a bug that
    // swapped in `toISOString().slice(0, 16)` would still pass under a UTC test runner.
    process.env.TZ = "America/New_York";
  });

  afterEach(() => {
    process.env.TZ = originalTz;
  });

  it("formats an ISO instant using LOCAL wall time, not UTC", () => {
    // 2026-07-13T09:30:00Z is 05:30 in America/New_York (EDT, UTC-4) in July.
    expect(toLocalDateTimeInput("2026-07-13T09:30:00Z")).toBe("2026-07-13T05:30");
  });

  it("differs from the naive toISOString().slice(0, 16) shortcut", () => {
    const instant = "2026-07-13T09:30:00Z";
    expect(toLocalDateTimeInput(instant)).not.toBe(new Date(instant).toISOString().slice(0, 16));
  });

  it("accepts a Date instance directly", () => {
    const date = new Date("2026-01-15T00:15:00Z"); // 2026-01-14T19:15 EST (UTC-5) in January
    expect(toLocalDateTimeInput(date)).toBe("2026-01-14T19:15");
  });
});
