import { describe, expect, it } from "vitest";

import type { AlternativesResponse } from "./api";
import type { BrandIndexItem } from "./brand-index";
import {
  EMPTY_LIST,
  FORMAT_VERSION,
  cleanTimes,
  compare,
  fromRanking,
  itemKey,
  merge,
  migrate,
  parseList,
  parseListText,
  remove,
  update,
  upsert,
  type SavedMedicine,
} from "./my-medicines";

const seclo: SavedMedicine = {
  brandCode: "BR00022",
  brandName: "Seclo",
  genericName: "Omeprazole",
  strength: "20 mg",
  dosageForm: "capsule",
  unitsPerDay: 2,
  reminderTimes: ["08:00"],
  addedOn: "2026-11-01",
};
// A version 1 item: same fields, but a database id instead of the brand code.
const secloV1 = { ...seclo, brandCode: undefined, brandId: 22, genericId: 4 };

function brand(code: string, id: number, name: string, strength = "20 mg", form = "capsule"): BrandIndexItem {
  return {
    code,
    id,
    name,
    generic_id: 4,
    generic: "Omeprazole",
    strength,
    dosage_form: form,
    manufacturer: "M",
    price_per_unit: 5,
    price_checked_on: "2026-11-13",
    rank: 1,
    group_size: 3,
    approvals: 2,
  };
}

describe("parseList (storage format)", () => {
  it("reads version 2", () => {
    expect(parseList({ version: FORMAT_VERSION, items: [seclo] })).toEqual({ version: 2, items: [seclo] });
  });

  it("keeps version 1 and unversioned lists aside until they can be migrated", () => {
    for (const raw of [{ version: 1, items: [secloV1] }, [secloV1], { items: [secloV1] }]) {
      const list = parseList(raw);
      expect(list.items).toEqual([]);
      expect(list.legacy).toHaveLength(1);
      expect(list.legacy?.[0]).toMatchObject({ brandId: 22, brandName: "Seclo", unitsPerDay: 2 });
    }
  });

  it("refuses an unknown future version instead of guessing", () => {
    expect(parseList({ version: 99, items: [seclo] })).toEqual(EMPTY_LIST);
  });

  it("drops invalid items and unknown fields, keeps one entry per brand", () => {
    const list = parseList({
      version: 2,
      items: [
        { ...seclo, patientName: "Rahim", photo: "data:..." },
        { ...seclo, brandName: "Duplicate" },
        { ...seclo, brandCode: "22" }, // not a code
        null,
      ],
    });
    expect(list.items).toEqual([seclo]);
    expect(Object.keys(list.items[0])).not.toContain("patientName");
  });

  it("cleans units and times the user did not give properly", () => {
    const [item] = parseList({ version: 2, items: [{ ...seclo, unitsPerDay: -3, reminderTimes: ["25:00", "20:00", "08:00", "08:00", 7] }] }).items;
    expect(item.unitsPerDay).toBeNull();
    expect(item.reminderTimes).toEqual(["08:00", "20:00"]);
  });

  it("treats broken text as an empty list", () => {
    expect(parseListText("{not json")).toEqual(EMPTY_LIST);
    expect(parseListText(null)).toEqual(EMPTY_LIST);
  });
});

describe("migrate (version 1 -> codes)", () => {
  it("matches by brand, strength and form, even when the old id now belongs to another brand", () => {
    const index = [brand("BR00030", 22, "Losectil"), brand("BR00022", 31, "Seclo")];
    const list = migrate(parseList({ version: 1, items: [secloV1] }), index);
    expect(list.legacy).toBeUndefined();
    expect(list.items).toEqual([seclo]); // the user's amount, times and day are kept
  });

  it("falls back to the old id when the name changed but strength and form agree", () => {
    const index = [brand("BR00077", 22, "Seclo MUPS")];
    expect(migrate(parseList([secloV1]), index).items[0].brandCode).toBe("BR00077");
  });

  it("keeps a brand that is no longer listed, without a code", () => {
    const list = migrate(parseList([secloV1]), [brand("BR00022", 22, "Seclo", "40 mg")]);
    expect(list.items).toEqual([{ ...seclo, brandCode: null }]);
    expect(itemKey(list.items[0])).toBe("name:seclo|20 mg|capsule");
  });
});

describe("changes", () => {
  it("saving the same brand twice updates it and keeps the first-saved day", () => {
    const once = upsert(EMPTY_LIST, seclo);
    const twice = upsert(once, { ...seclo, unitsPerDay: 1, reminderTimes: [], addedOn: "2026-11-09" });
    expect(twice.items).toHaveLength(1);
    expect(twice.items[0]).toMatchObject({ unitsPerDay: 1, reminderTimes: ["08:00"], addedOn: "2026-11-01" });
  });

  it("updates, removes and merges imports (also an old exported file)", () => {
    let list = upsert(EMPTY_LIST, seclo);
    list = update(list, "BR00022", { reminderTimes: ["21:00", "07:30"], unitsPerDay: null });
    expect(list.items[0]).toMatchObject({ reminderTimes: ["07:30", "21:00"], unitsPerDay: null });
    const napa = { ...seclo, brandCode: "BR00001", brandName: "Napa", genericName: "Paracetamol" };
    const merged = merge(list, { version: 2, items: [napa, { ...seclo, unitsPerDay: 3 }] });
    expect(merged.items.map((m) => [m.brandName, m.unitsPerDay])).toEqual([
      ["Seclo", 3],
      ["Napa", 2],
    ]);
    expect(merge(list, parseList([secloV1])).legacy).toHaveLength(1);
    expect(remove(list, "BR00022")).toEqual({ version: 2, items: [], legacy: undefined });
  });

  it("only accepts HH:MM times", () => {
    expect(cleanTimes(["8:00", "08:00", "23:59", "24:00", "12:60"])).toEqual(["08:00", "23:59"]);
  });

  it("builds a saved medicine from a ranking page, by code", () => {
    const item = fromRanking(
      { generic: { id: 4, name: "Omeprazole" }, strength: "20 mg", dosage_form: "capsule" } as never,
      { code: "BR00022", name: "Seclo" },
      2,
    );
    expect(item).toMatchObject({ brandCode: "BR00022", genericName: "Omeprazole", unitsPerDay: 2, reminderTimes: [] });
    expect(Object.keys(item)).not.toContain("brandId");
  });
});

function ranking(brands: [string, string, number][]): AlternativesResponse {
  return {
    selected_brand_id: null,
    selected_brand_code: null,
    generic: { id: 4, name: "Omeprazole" },
    strength: "20 mg",
    dosage_form: "capsule",
    disclaimer: "",
    alternatives: brands.map(([code, name, price], i) => ({
      brand_id: i + 100,
      code,
      name,
      price_per_unit: price,
      rank: i + 1,
      manufacturer: { name: `${name} Ltd` },
    })),
  } as unknown as AlternativesResponse;
}

describe("compare (rank comparison)", () => {
  it("shows the top-ranked brand and the difference per 30 units and per month", () => {
    const c = compare(seclo, ranking([["BR00030", "Losectil", 5], ["BR00022", "Seclo", 6], ["BR00031", "Proceptin", 5]]));
    expect(c).toMatchObject({ rank: 2, total: 3, samePrice: false, differencePer30: -30, differencePerMonth: -60 });
    expect(c?.top).toMatchObject({ code: "BR00030", name: "Losectil", manufacturer: "Losectil Ltd", price: 5 });
  });

  it("says when the higher-ranked one costs the same", () => {
    const c = compare(seclo, ranking([["BR00030", "Losectil", 6], ["BR00022", "Seclo", 6]]));
    expect(c).toMatchObject({ samePrice: true, differencePer30: 0 });
  });

  it("no monthly figure without units per day; nothing to compare when already top", () => {
    expect(compare({ ...seclo, unitsPerDay: null }, ranking([["BR00030", "L", 5], ["BR00022", "S", 6]]))?.differencePerMonth).toBeNull();
    expect(compare(seclo, ranking([["BR00022", "Seclo", 6], ["BR00030", "L", 5]]))).toMatchObject({ rank: 1, top: null });
  });

  it("returns null when the brand is no longer in the group", () => {
    expect(compare(seclo, ranking([["BR00030", "Losectil", 5]]))).toBeNull();
  });
});
