import { describe, expect, it } from "vitest";
import { categoryChipTint, categoryColorVar } from "./categoryColor";

describe("categoryColorVar", () => {
  it("maps a known palette key to its CSS var", () => {
    expect(categoryColorVar("blue")).toBe("var(--cat-blue)");
    expect(categoryColorVar("slate")).toBe("var(--cat-slate)");
  });

  it("passes through valid hex colors as-is", () => {
    expect(categoryColorVar("#e3db38")).toBe("#e3db38");
    expect(categoryColorVar("#F59F00")).toBe("#F59F00");
    expect(categoryColorVar("#123")).toBe("#123");
    expect(categoryColorVar("#12345678")).toBe("#12345678");
  });

  it("falls back to slate for invalid or missing values", () => {
    expect(categoryColorVar("not-a-color")).toBe("var(--cat-slate)");
    expect(categoryColorVar("#zzzzzz")).toBe("var(--cat-slate)");
    expect(categoryColorVar("#12345")).toBe("var(--cat-slate)");
    expect(categoryColorVar(null)).toBe("var(--cat-slate)");
    expect(categoryColorVar(undefined)).toBe("var(--cat-slate)");
    expect(categoryColorVar("")).toBe("var(--cat-slate)");
  });
});

describe("categoryChipTint", () => {
  it("builds a color-mix expression using the resolved color for each input type", () => {
    expect(categoryChipTint("blue")).toBe("color-mix(in srgb, var(--cat-blue) 16%, transparent)");
    expect(categoryChipTint("#e3db38")).toBe("color-mix(in srgb, #e3db38 16%, transparent)");
    expect(categoryChipTint(null)).toBe("color-mix(in srgb, var(--cat-slate) 16%, transparent)");
  });
});
