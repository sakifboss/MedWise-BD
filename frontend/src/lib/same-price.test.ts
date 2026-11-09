import { describe, expect, it } from "vitest";

import { samePrice } from "./same-price";

const prices = (...values: number[]) => values.map((price_per_unit) => ({ price_per_unit }));

describe("samePrice", () => {
  it("returns the price when every brand costs the same", () => {
    expect(samePrice(prices(1.2, 1.2, 1.2, 1.2, 1.2, 1.2))).toBe(1.2);
  });

  it("returns null when prices differ", () => {
    expect(samePrice(prices(5, 5, 6))).toBeNull();
  });

  it("treats prices equal to the poisha as the same", () => {
    expect(samePrice(prices(1.2, 1.2000001))).toBe(1.2);
    expect(samePrice(prices(15, 15.05))).toBeNull();
  });

  it("returns null for a single brand (nothing to compare)", () => {
    expect(samePrice(prices(3))).toBeNull();
  });

  it("returns null for an empty group", () => {
    expect(samePrice([])).toBeNull();
  });
});
