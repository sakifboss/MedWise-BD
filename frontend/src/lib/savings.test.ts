import { describe, expect, it } from "vitest";

import { isPerBottle, monthlyCost, parseQuantity, quantityUnit } from "./savings";

describe("quantityUnit", () => {
  it("counts bottles a month for bottled forms", () => {
    for (const form of ["suspension", "eye drops"]) {
      expect(isPerBottle(form)).toBe(true);
      expect(quantityUnit(form)).toMatchObject({ perMonth: 1, step: 1, max: 20 });
    }
  });

  it("counts units a day for tablets and capsules", () => {
    for (const form of ["tablet", "capsule"]) {
      expect(isPerBottle(form)).toBe(false);
      expect(quantityUnit(form)).toMatchObject({ perMonth: 30, step: 0.5, max: 24 });
    }
  });

  it("prices a month from the user's own number", () => {
    expect(monthlyCost(34.5, 2, quantityUnit("eye drops"))).toBe(69);
    expect(monthlyCost(1.2, 2, quantityUnit("tablet"))).toBeCloseTo(72);
    expect(parseQuantity("21", quantityUnit("eye drops"))).toBeNull();
    expect(parseQuantity("3", quantityUnit("eye drops"))).toBe(3);
  });
});
