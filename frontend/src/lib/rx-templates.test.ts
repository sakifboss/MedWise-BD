import { describe, expect, it } from "vitest";

import type { BrandIndexItem } from "./brand-index";
import { newLine, type RxLine, type RxSource } from "./rx";
import { appendText, applyLines, fromTemplateLine, toTemplateLines, type Catalog } from "./rx-templates";

const NAPA: BrandIndexItem = {
  code: "BR00001",
  id: 1,
  name: "Napa",
  generic_id: 1,
  generic: "Paracetamol",
  strength: "500 mg",
  dosage_form: "tablet",
  manufacturer: "Beximco Pharmaceuticals Ltd",
  price_per_unit: 1.2,
  price_checked_on: "2026-11-13",
  rank: 3,
  group_size: 7,
  approvals: 2,
};
const CATALOG: Catalog = { brands: new Map([["BR00001", NAPA]]), generics: new Map([["Metformin", 12], ["Paracetamol", 1]]) };
const BRAND_SOURCE: RxSource = {
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
  rank: 3,
  groupSize: 7,
  approvals: 2,
};

const PAD: RxLine[] = [
  {
    ...newLine(BRAND_SOURCE, "a"),
    pattern: "1+0+1",
    food: "after",
    duration: { kind: "fixed", n: 5, unit: "days" },
    substitution: true,
    note: "if fever is over 101°F",
  },
  { ...newLine({ kind: "generic", genericId: 12, generic: "Metformin", strength: "500 mg", dosageForm: "tablet" }, "b"), pattern: "1+0+1", duration: { kind: "continue" } },
  { ...newLine({ kind: "free", name: "Ambrox syrup" }, "c"), pattern: "2+2+2", unit: "spoon" },
];

describe("templates", () => {
  it("keep medicine lines only, and come back the same", () => {
    const saved = toTemplateLines(PAD);
    expect(saved[0]).toMatchObject({ kind: "brand", code: "BR00001", name: "Napa", duration: "5d", substitution: true, note: "if fever is over 101°F" });
    expect(saved[1]).toMatchObject({ kind: "generic", generic: "Metformin", duration: "c", substitution: false });
    expect(saved[2]).toMatchObject({ kind: "free", name: "Ambrox syrup", unit: "spoon" });
    const back = saved.map((line, i) => fromTemplateLine({ ...line, gone: false }, CATALOG, `n${i}`));
    expect(back.every((b) => !b.asWritten)).toBe(true);
    expect(back.map((b) => ({ ...b.line, id: "" }))).toEqual(PAD.map((l) => ({ ...l, id: "" })));
  });

  it("turn a brand or generic MedWise no longer has into a line as written", () => {
    const [brand, generic] = toTemplateLines(PAD);
    const empty: Catalog = { brands: new Map(), generics: new Map() };
    const a = fromTemplateLine({ ...brand, gone: false }, empty, "x");
    expect(a.asWritten).toBe(true);
    expect(a.line.source).toEqual({ kind: "free", name: "Napa" });
    expect(a.line.substitution).toBe(false);
    const b = fromTemplateLine({ ...generic, gone: false }, empty, "y");
    expect(b.line.source).toEqual({ kind: "free", name: "Metformin 500 mg" });
    const gone = fromTemplateLine({ ...toTemplateLines([PAD[2]])[0], name: "Oldbrand", gone: true }, CATALOG, "z");
    expect(gone.asWritten).toBe(true);
  });

  it("apply within the 12-line limit and add text after what is there", () => {
    const eleven = Array.from({ length: 11 }, (_, i) => ({ ...PAD[2], id: `p${i}` }));
    const { lines, skipped } = applyLines(eleven, PAD);
    expect([lines.length, skipped]).toEqual([12, 2]);
    expect(appendText("", "CBC")).toBe("CBC");
    expect(appendText("RBS\n", "CBC")).toBe("RBS\nCBC");
    expect(appendText("RBS", "  ")).toBe("RBS");
  });
});
