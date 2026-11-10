import { describe, expect, it } from "vitest";

import type { AlternativesResponse } from "./api";
import {
  EMPTY_LIST,
  FORMAT_VERSION,
  cleanTimes,
  compare,
  fromRanking,
  merge,
  parseList,
  parseListText,
  remove,
  update,
  upsert,
  type SavedMedicine,
} from "./my-medicines";

const seclo: SavedMedicine = {
  brandId: 22,
  brandName: "Seclo",
  genericId: 4,
  genericName: "Omeprazole",
  strength: "20 mg",
  dosageForm: "capsule",
  unitsPerDay: 2,
  reminderTimes: ["08:00"],
  addedOn: "2026-11-01",
};

describe("parseList (storage format and migration)", () => {
  it("reads the current format", () => {
    expect(parseList({ version: FORMAT_VERSION, items: [seclo] })).toEqual({ version: 1, items: [seclo] });
  });

  it("migrates an unversioned array and a version-less object", () => {
    expect(parseList([seclo]).items).toEqual([seclo]);
    expect(parseList({ items: [seclo] }).items).toEqual([seclo]);
  });

  it("refuses an unknown future version instead of guessing", () => {
    expect(parseList({ version: 99, items: [seclo] })).toEqual(EMPTY_LIST);
  });

  it("drops invalid items and unknown fields, keeps one entry per brand", () => {
    const list = parseList({
      version: 1,
      items: [
        { ...seclo, patientName: "Rahim", photo: "data:..." },
        { ...seclo, brandName: "Duplicate" },
        { brandId: "x", brandName: "Bad" },
        null,
      ],
    });
    expect(list.items).toHaveLength(1);
    expect(list.items[0]).toEqual(seclo);
    expect(Object.keys(list.items[0])).not.toContain("patientName");
  });

  it("cleans units and times the user did not give properly", () => {
    const [item] = parseList([{ ...seclo, unitsPerDay: -3, reminderTimes: ["25:00", "20:00", "08:00", "08:00", 7] }]).items;
    expect(item.unitsPerDay).toBeNull();
    expect(item.reminderTimes).toEqual(["08:00", "20:00"]);
  });

  it("treats broken text as an empty list", () => {
    expect(parseListText("{not json")).toEqual(EMPTY_LIST);
    expect(parseListText(null)).toEqual(EMPTY_LIST);
  });
});

describe("changes", () => {
  it("saving the same brand twice updates it and keeps the first-saved day", () => {
    const once = upsert(EMPTY_LIST, seclo);
    const twice = upsert(once, { ...seclo, unitsPerDay: 1, reminderTimes: [], addedOn: "2026-11-09" });
    expect(twice.items).toHaveLength(1);
    expect(twice.items[0]).toMatchObject({ unitsPerDay: 1, reminderTimes: ["08:00"], addedOn: "2026-11-01" });
  });

  it("updates, removes and merges imports", () => {
    let list = upsert(EMPTY_LIST, seclo);
    list = update(list, 22, { reminderTimes: ["21:00", "07:30"], unitsPerDay: null });
    expect(list.items[0]).toMatchObject({ reminderTimes: ["07:30", "21:00"], unitsPerDay: null });
    const napa = { ...seclo, brandId: 1, brandName: "Napa", genericId: 1, genericName: "Paracetamol" };
    expect(merge(list, { version: 1, items: [napa, { ...seclo, unitsPerDay: 3 }] }).items.map((m) => [m.brandName, m.unitsPerDay])).toEqual([
      ["Seclo", 3],
      ["Napa", 2],
    ]);
    expect(remove(list, 22)).toEqual(EMPTY_LIST);
  });

  it("only accepts HH:MM times", () => {
    expect(cleanTimes(["8:00", "08:00", "23:59", "24:00", "12:60"])).toEqual(["08:00", "23:59"]);
  });

  it("builds a saved medicine from a ranking page", () => {
    const item = fromRanking(
      { generic: { id: 4, name: "Omeprazole" }, strength: "20 mg", dosage_form: "capsule" } as never,
      { brand_id: 22, name: "Seclo" },
      2,
    );
    expect(item).toMatchObject({ brandId: 22, genericId: 4, unitsPerDay: 2, reminderTimes: [] });
  });
});

function ranking(brands: [number, string, number][]): AlternativesResponse {
  return {
    selected_brand_id: null,
    generic: { id: 4, name: "Omeprazole" },
    strength: "20 mg",
    dosage_form: "capsule",
    disclaimer: "",
    alternatives: brands.map(([brand_id, name, price], i) => ({
      brand_id,
      name,
      price_per_unit: price,
      rank: i + 1,
      manufacturer: { name: `${name} Ltd` },
    })),
  } as unknown as AlternativesResponse;
}

describe("compare (rank comparison)", () => {
  it("shows the top-ranked brand and the difference per 30 units and per month", () => {
    const c = compare(seclo, ranking([[30, "Losectil", 5], [22, "Seclo", 6], [31, "Proceptin", 5]]));
    expect(c).toMatchObject({ rank: 2, total: 3, samePrice: false, differencePer30: -30, differencePerMonth: -60 });
    expect(c?.top).toMatchObject({ name: "Losectil", manufacturer: "Losectil Ltd", price: 5 });
  });

  it("says when the higher-ranked one costs the same", () => {
    const c = compare(seclo, ranking([[30, "Losectil", 6], [22, "Seclo", 6]]));
    expect(c).toMatchObject({ samePrice: true, differencePer30: 0 });
  });

  it("no monthly figure without units per day; nothing to compare when already top", () => {
    expect(compare({ ...seclo, unitsPerDay: null }, ranking([[30, "L", 5], [22, "S", 6]]))?.differencePerMonth).toBeNull();
    expect(compare(seclo, ranking([[22, "Seclo", 6], [30, "L", 5]]))).toMatchObject({ rank: 1, top: null });
  });

  it("returns null when the brand is no longer in the group", () => {
    expect(compare(seclo, ranking([[30, "Losectil", 5]]))).toBeNull();
  });
});
