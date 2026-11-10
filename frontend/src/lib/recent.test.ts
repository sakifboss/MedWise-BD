import { describe, expect, it } from "vitest";

import {
  EMPTY_RECENT,
  MAX_RECENT,
  RECENT_VERSION,
  addRecent,
  parseRecent,
  recentFor,
  toRecentItem,
  type RecentItem,
} from "./recent";

const NOW = new Date(2026, 10, 11, 9, 0);
const seclo = recentFor(
  { kind: "alternatives", brandId: 22, brandName: "Seclo" },
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
      href: "/alternatives/22",
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
    for (let i = 1; i <= 12; i++) list = addRecent(list, { ...seclo, href: `/alternatives/${i}` });
    expect(list.items).toHaveLength(MAX_RECENT);
    expect(list.items[0].href).toBe("/alternatives/12");
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
      "/alternatives/22?x=<script>",
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
