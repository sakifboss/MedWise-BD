import { describe, expect, it } from "vitest";

import { newLine, type RxLine, type RxSource } from "./rx";
import {
  buildRxLink,
  canonical,
  decodePayload,
  encodePayload,
  parseCanonical,
  parseRxFragment,
  readRxLink,
  sha256Hex,
  toPayload,
} from "./rx-payload";

const BRAND: RxSource = {
  kind: "brand",
  code: "BR00042",
  name: "Seclo",
  genericId: 4,
  generic: "Omeprazole",
  strength: "20 mg",
  dosageForm: "capsule",
  manufacturer: "Square Pharmaceuticals PLC",
  pricePerUnit: 6,
  priceCheckedOn: "2026-11-13",
  rank: 2,
  groupSize: 7,
  approvals: 2,
};

const LINES: RxLine[] = [
  { ...newLine(BRAND, "a"), pattern: "1+0+1", food: "before", duration: { kind: "fixed", n: 14, unit: "days" }, substitution: true, note: "secret note" },
  { ...newLine({ kind: "generic", genericId: 1, generic: "Paracetamol", strength: "500 mg", dosageForm: "tablet" }, "b"), pattern: "½+0+½", duration: { kind: "continue" } },
  { ...newLine({ kind: "free", name: "Ambrox syrup" }, "c"), pattern: "as needed", unit: "spoon", duration: { kind: "fixed", n: 1, unit: "months" } },
];
const SIG = { doctorId: 12, issuedAt: 1794586743, sig: "A".repeat(43) };

describe("payload", () => {
  it("holds only medicine lines and dates (no notes or patient fields)", () => {
    const text = canonical(toPayload(LINES, "2026-11-13", "2026-11-27"));
    expect(text).toBe(
      '{"v":1,"d":"2026-11-13","f":"2026-11-27","l":[[42,"1+0+1",1,1,"14d",1],' +
        '["g","Paracetamol","500 mg","tablet","½+0+½",0,0,"c",0],["t","Ambrox syrup","as needed",2,0,"1m"]]}',
    );
    expect(text).not.toContain("secret note");
  });

  it("round-trips through the QR link", async () => {
    const payload = toPayload(LINES, "2026-11-13", "");
    const text = canonical(payload);
    const encoded = await encodePayload(text);
    expect(encoded.startsWith("z")).toBe(true);
    const link = buildRxLink("https://medwise-bd.vercel.app", encoded, SIG);
    const read = await readRxLink(new URL(link).hash);
    expect(read.text).toBe(text);
    expect(read.payload).toEqual(payload);
    expect(read.signature).toEqual(SIG);
    expect(await sha256Hex(read.text)).toBe(await sha256Hex(text));
    expect(await decodePayload("p" + Buffer.from(text).toString("base64url"))).toBe(text);
  });

  it("rejects payloads that are not exactly ours", () => {
    const good = JSON.parse(canonical(toPayload(LINES, "2026-11-13", "")));
    const bad = [
      { ...good, v: 2 },
      { ...good, d: "13/11/2026" },
      { ...good, l: [] },
      { ...good, l: Array(13).fill(good.l[0]) },
      { ...good, l: [[0, "1", 0, 0, "", 1]] },
      { ...good, l: [[42, "1", 9, 0, "", 1]] },
      { ...good, l: [[42, "1", 0, 0, "400d", 1]] },
      { ...good, l: [["t", "x".repeat(41), "1", 0, 0, ""]] },
      { ...good, l: [["x", "y"]] },
    ];
    for (const value of bad) expect(() => parseCanonical(JSON.stringify(value))).toThrow();
  });

  it("never crashes on broken or random links", async () => {
    const samples = ["", "#", "#abc", "#z.1.2.3", `#zAAAA.1.2.${"A".repeat(43)}`, `#q${"A".repeat(10)}.1.2.${"A".repeat(43)}`];
    let seed = 7;
    const random = () => ((seed = (seed * 1103515245 + 12345) % 2 ** 31) / 2 ** 31);
    const alphabet = "zpABCxyz019-_.";
    for (let i = 0; i < 300; i++) {
      samples.push("#" + Array.from({ length: Math.floor(random() * 80) }, () => alphabet[Math.floor(random() * alphabet.length)]).join(""));
    }
    for (const hash of samples) {
      const result = await readRxLink(hash).then(
        () => "ok",
        (error: unknown) => (error instanceof Error ? "error" : "other"),
      );
      expect(result).toBe("error");
    }
  });

  it("parses only well-formed fragments", () => {
    expect(parseRxFragment(`#zAbC.12.1794586743.${"A".repeat(43)}`)).toEqual({ encoded: "zAbC", ...SIG });
    for (const hash of [`#zAbC.0.1.${"A".repeat(43)}`, `#zAbC.12.1.${"A".repeat(42)}`, "#zAbC.12.1", `#x.12.1.${"A".repeat(43)}`]) {
      expect(parseRxFragment(hash)).toBeNull();
    }
  });
});
