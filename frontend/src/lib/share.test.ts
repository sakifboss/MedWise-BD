import { describe, expect, it } from "vitest";

import { parseShareItems, shareHref, shareItem } from "./share";

describe("share links", () => {
  it("new links use the brand code", () => {
    const item = shareItem({ kind: "brand", brand_id: 22, brand_code: "BR00022" } as never, 2);
    expect(item).toEqual({ kind: "brand", ref: "BR00022", quantity: 2 });
    expect(shareHref([item])).toBe("/share?m=c%3ABR00022%3A2");
  });

  it("links made before codes existed still open", () => {
    expect(parseShareItems("b:22:2")).toEqual([{ kind: "brand", ref: "22", quantity: 2 }]);
  });

  it("round-trips codes and generics, skipping bad and duplicate entries", () => {
    const items = parseShareItems(["c:br00042:", "c:BR00042:3", "g:12:500 mg:tablet:", "c:XX1:", "b:0:", "z:1"]);
    expect(items).toEqual([
      { kind: "brand", ref: "BR00042", quantity: null },
      { kind: "generic", genericId: 12, strength: "500 mg", dosageForm: "tablet", quantity: null },
    ]);
    expect(parseShareItems(new URLSearchParams(shareHref(items).split("?")[1]).getAll("m"))).toEqual(items);
  });
});
