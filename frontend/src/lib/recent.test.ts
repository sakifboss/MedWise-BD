import { describe, expect, it } from "vitest";

import type { BrandIndexItem } from "./brand-index";
import {
  EMPTY_RECENT,
  MAX_RECENT,
  RECENT_VERSION,
  addRecent,
  migrateRecent,
  parseRecent,
  recentFor,
  toRecentItem,
  type RecentItem,
} from "./recent";

const NOW = new Date(2026, 10, 11, 9, 0);
const seclo = recentFor(
  { kind: "alternatives", brandCode: "BR00022", brandName: "Seclo" },
  { genericName: "Omeprazole", strength: "20 mg", dosageForm: "capsule" },
  NOW,
);
const omeprazole = recentFor(
  { kind: "ranking", genericId: 4 },
  { genericName: "Omeprazole", strength: "20 mg", dosageForm: "capsule" },
  NOW,
);

describe("recentFor", () => {
  it("builds the item and link for each kind of page, with no price", () => {
    expect(seclo).toEqual({
      kind: "alternatives",
      name: "Seclo",
      genericName: "Omeprazole",
      strength: "20 mg",
      dosageForm: "capsule",
      href: "/alternatives/BR00022",
      viewedOn: "2026-11-11",
    });
    expect(omeprazole.name).toBe("Omeprazole");
    expect(omeprazole.href).toBe("/generics/4/ranking?strength=20+mg&form=capsule");
    expect(Object.keys(seclo)).not.toContain("price");
  });
});

describe("addRecent", () => {
  it("puts the newest first, moves a page to the top when opened again", () => {
    let list = addRecent(EMPTY_RECENT, seclo);
    list = addRecent(list, omeprazole);
    expect(list.items.map((i) => i.href)).toEqual([omeprazole.href, seclo.href]);
    list = addRecent(list, seclo);
    expect(list.items.map((i) => i.href)).toEqual([seclo.href, omeprazole.href]);
  });

  it(`keeps at most ${MAX_RECENT}`, () => {
    let list = EMPTY_RECENT;
    for (let i = 1; i <= 12; i++) list = addRecent(list, { ...seclo, href: `/alternatives/BR${String(i).padStart(5, "0")}` });
    expect(list.items).toHaveLength(MAX_RECENT);
    expect(list.items[0].href).toBe("/alternatives/BR00012");
  });
});

describe("parseRecent (storage format)", () => {
  const stored = (items: unknown[], version: unknown = RECENT_VERSION) => JSON.stringify({ version, items });

  it("reads the current format and drops duplicates", () => {
    expect(parseRecent(stored([seclo, omeprazole, seclo])).items).toEqual([seclo, omeprazole]);
  });

  it("treats broken text, missing data or an unknown version as empty", () => {
    expect(parseRecent(null)).toEqual(EMPTY_RECENT);
    expect(parseRecent("{not json")).toEqual(EMPTY_RECENT);
    expect(parseRecent(stored([seclo], 99))).toEqual(EMPTY_RECENT);
    expect(parseRecent(JSON.stringify([seclo]))).toEqual(EMPTY_RECENT);
  });

  it("only keeps links to our own ranking and alternatives pages", () => {
    const bad = (href: string): RecentItem => ({ ...seclo, href });
    for (const href of [
      "https://evil.example/alternatives/22",
      "//evil.example",
      "javascript:alert(1)",
      "/alternatives/BR00022?x=<script>",
      "/alternatives/22", // version 1 (id) links are only read for migration
      "/my-medicines",
      "/generics/4/ranking?strength=20+mg&form=capsule#x",
    ]) {
      expect(toRecentItem(bad(href)), href).toBeNull();
    }
  });

  it("drops invalid items and unknown fields (like a price)", () => {
    const list = parseRecent(stored([{ ...seclo, price: 6, patient: "Rahim" }, { kind: "x" }, null]));
    expect(list.items).toEqual([seclo]);
    expect(Object.keys(list.items[0])).not.toContain("price");
  });
});

describe("version 1 lists (brand links by id)", () => {
  const v1 = JSON.stringify({
    version: 1,
    items: [
      { ...seclo, href: "/alternatives/22", viewedOn: "2026-11-12" },
      { ...omeprazole, viewedOn: "2026-11-10" },
      { ...seclo, name: "Gone", href: "/alternatives/99", viewedOn: "2026-11-11" },
    ],
  });
  const index = [
    { code: "BR00030", id: 22, name: "Losectil", generic: "Omeprazole", strength: "20 mg", dosage_form: "capsule" },
    { code: "BR00022", id: 31, name: "Seclo", generic: "Omeprazole", strength: "20 mg", dosage_form: "capsule" },
  ] as BrandIndexItem[];

  it("keeps ranking links and sets brand links aside", () => {
    const list = parseRecent(v1);
    expect(list.items.map((i) => i.href)).toEqual([omeprazole.href]);
    expect(list.legacy?.map((i) => i.href)).toEqual(["/alternatives/22", "/alternatives/99"]);
  });

  it("matches brand links to codes by brand details (not the old id) and keeps the order", () => {
    const list = migrateRecent(parseRecent(v1), index);
    expect(list.legacy).toBeUndefined();
    expect(list.items.map((i) => i.href)).toEqual(["/alternatives/BR00022", omeprazole.href]);
  });

  it("pending items survive a page view before the migration", () => {
    const pending = parseRecent(v1);
    const stored = JSON.stringify(addRecent(pending, omeprazole));
    expect(parseRecent(stored).legacy).toHaveLength(2);
  });
});
