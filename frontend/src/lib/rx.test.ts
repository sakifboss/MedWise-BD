import { describe, expect, it } from "vitest";

import {
  amountText,
  catalogGenericIds,
  duplicateGenerics,
  estimatedCost,
  formWordFor,
  instruction,
  newLine,
  parsePattern,
  totalUnits,
  unitFor,
  type RxLine,
  type RxSource,
} from "./rx";
import { SearchCache, SearchPacer, searchKey } from "./rx-search";

const BRAND: RxSource = {
  kind: "brand",
  code: "BR00001",
  name: "Napa",
  genericId: 1,
  generic: "Paracetamol",
  strength: "500 mg",
  dosageForm: "tablet",
  manufacturer: "Beximco Pharmaceuticals Ltd",
  pricePerUnit: 1.2,
  priceCheckedOn: "2026-11-13",
  rank: 2,
  groupSize: 7,
  approvals: 2,
};

function line(overrides: Partial<RxLine>): RxLine {
  return { ...newLine(BRAND, "l1"), ...overrides };
}

describe("dose patterns", () => {
  it("reads 3 and 4 slots with halves and Bangla digits", () => {
    expect(parsePattern("1+0+1")).toEqual([1, 0, 1]);
    expect(parsePattern(" ½ + 0 + 1½ ")).toEqual([0.5, 0, 1.5]);
    expect(parsePattern("১+০+১+০")).toEqual([1, 0, 1, 0]);
    expect(parsePattern("2+2+2+2")).toEqual([2, 2, 2, 2]);
  });

  it("treats anything else as free text", () => {
    for (const text of ["as needed", "1+1", "1+1+1+1+1", "1+a+1", "", "+++", "1.5+0+1", "30+0+0"]) {
      expect(parsePattern(text)).toBeNull();
    }
  });

  it("writes amounts", () => {
    expect([amountText(1.5, "en"), amountText(0.5, "bn"), amountText(30, "bn"), amountText(22.5, "bn")]).toEqual([
      "1½",
      "½",
      "৩০",
      "২২½",
    ]);
  });
});

describe("the patient instruction", () => {
  it("matches the example in Claude.MD", () => {
    const l = line({ pattern: "0+0+1", food: "after", duration: { kind: "fixed", n: 30, unit: "days" } });
    expect(instruction(l, "en")).toBe("1 at night, after food — 30 days (30 in total)");
    expect(instruction(l, "bn")).toBe("রাতে ১টি, খাবারের পরে — ৩০ দিন (মোট ৩০টি)");
  });

  it("names every slot taken, with halves", () => {
    const l = line({ pattern: "1+½+1", food: "before", duration: { kind: "fixed", n: 2, unit: "weeks" } });
    expect(instruction(l, "en")).toBe("1 in the morning, ½ at noon and 1 at night, before food — 2 weeks (35 in total)");
    expect(instruction(l, "bn")).toBe("সকালে ১টি ও দুপুরে ½টি ও রাতে ১টি, খাবারের আগে — ২ সপ্তাহ (মোট ৩৫টি)");
  });

  it("reads four slots as times a day", () => {
    const same = line({ pattern: "1+1+1+1", duration: { kind: "fixed", n: 5, unit: "days" } });
    expect(instruction(same, "en")).toBe("1, 4 times a day — 5 days (20 in total)");
    expect(instruction(same, "bn")).toBe("দিনে ৪ বার, প্রতিবার ১টি — ৫ দিন (মোট ২০টি)");
    const mixed = line({ pattern: "1+½+1+0" });
    expect(instruction(mixed, "en")).toBe("3 times a day (1 + ½ + 1 + 0)");
    expect(instruction(mixed, "bn")).toBe("দিনে ৩ বার (১ + ½ + ১ + ০)");
  });

  it("keeps free text as written and leaves out missing parts", () => {
    const l = line({ pattern: "as needed for fever", food: "after" });
    expect(instruction(l, "en")).toBe("as needed for fever, after food");
    expect(instruction(line({ pattern: "" }), "en")).toBe("");
    expect(instruction(line({ duration: { kind: "continue" } }), "bn")).toBe("চলবে");
    expect(instruction(line({ pattern: "1+0+1", duration: { kind: "continue" } }), "en")).toBe(
      "1 in the morning and 1 at night — continue",
    );
  });

  it("uses the unit words for spoons, drops and other units", () => {
    const syrup = line({ pattern: "2+0+2", unit: "spoon", duration: { kind: "fixed", n: 1, unit: "months" } });
    expect(instruction(syrup, "en")).toBe("2 spoons in the morning and 2 spoons at night — 1 month");
    expect(instruction(syrup, "bn")).toBe("সকালে ২ চামচ ও রাতে ২ চামচ — ১ মাস");
    const drops = line({ pattern: "1+1+1+1", unit: "drop" });
    expect(instruction(drops, "en")).toBe("1 drop, 4 times a day");
    expect(instruction(drops, "bn")).toBe("দিনে ৪ বার, প্রতিবার ১ ফোঁটা");
  });
});

describe("totals and cost", () => {
  it("counts only tablets and capsules with a fixed duration", () => {
    expect(totalUnits(line({ pattern: "1+0+1", duration: { kind: "fixed", n: 1, unit: "months" } }))).toBe(60);
    expect(totalUnits(line({ pattern: "½+0+½", duration: { kind: "fixed", n: 7, unit: "days" } }))).toBe(7);
    expect(totalUnits(line({ pattern: "1+0+1", duration: { kind: "continue" } }))).toBeNull();
    expect(totalUnits(line({ pattern: "as needed", duration: { kind: "fixed", n: 5, unit: "days" } }))).toBeNull();
    expect(
      totalUnits(line({ pattern: "1+0+1", unit: "spoon", duration: { kind: "fixed", n: 5, unit: "days" } })),
    ).toBeNull();
  });

  it("estimates cost only for catalog brands", () => {
    const l = line({ pattern: "1+0+1", duration: { kind: "fixed", n: 10, unit: "days" } });
    expect(estimatedCost(l)).toBe(24);
    expect(estimatedCost({ ...l, source: { kind: "free", name: "Ambrox" } })).toBeNull();
    expect(
      estimatedCost({ ...l, source: { kind: "generic", genericId: 1, generic: "Paracetamol", strength: "500 mg", dosageForm: "tablet" } }),
    ).toBeNull();
  });
});

describe("lines", () => {
  it("starts with no dose, and form word and unit from the dosage form", () => {
    const l = newLine({ ...BRAND, dosageForm: "suspension" } as RxSource, "x");
    expect([l.pattern, l.food, l.duration, l.substitution]).toEqual(["", "", { kind: "none" }, false]);
    expect([l.formWord, l.unit]).toEqual(["Susp.", "spoon"]);
    expect([formWordFor("eye drops"), unitFor("eye drops"), formWordFor("patch")]).toEqual(["Drop", "drop", "Patch"]);
  });

  it("finds the same generic twice and lists generic ids for the interaction check", () => {
    const lines = [
      line({ id: "a" }),
      line({ id: "b", source: { kind: "generic", genericId: 1, generic: "Paracetamol", strength: "500 mg", dosageForm: "tablet" } }),
      line({ id: "c", source: { ...BRAND, genericId: 7, generic: "Omeprazole" } as RxSource }),
      line({ id: "d", source: { kind: "free", name: "Ambrox" } }),
    ];
    expect(duplicateGenerics(lines)).toEqual([{ genericId: 1, generic: "Paracetamol", count: 2 }]);
    expect(catalogGenericIds(lines)).toEqual([1, 7]);
  });
});

describe("search pacing", () => {
  it("needs 2 characters and ignores case and spaces", () => {
    expect(searchKey(" N ")).toBeNull();
    expect(searchKey("  Na  PA ")).toBe("na pa");
  });

  it("never allows more than the limit in a minute", () => {
    let now = 0;
    const pacer = new SearchPacer(3, 60_000, () => now);
    for (let i = 0; i < 3; i++) {
      expect(pacer.delay()).toBe(0);
      pacer.record();
      now += 1000;
    }
    expect(pacer.delay()).toBe(57_000); // the first one leaves the window at 60 s
    now = 60_001;
    expect(pacer.delay()).toBe(0);
  });

  it("remembers the newest answers", () => {
    const cache = new SearchCache<number>(2);
    cache.set("a", 1);
    cache.set("b", 2);
    cache.get("a");
    cache.set("c", 3);
    expect([cache.get("a"), cache.get("b"), cache.get("c")]).toEqual([1, undefined, 3]);
  });
});
