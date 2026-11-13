import { afterEach, describe, expect, it, vi } from "vitest";

import {
  DEFAULT_PRINT_LANGUAGE,
  RX_PREFS_KEY,
  loadPrintLanguage,
  parsePrintLanguage,
  savePrintLanguage,
} from "./rx-preferences";

function fakeStorage(): Storage {
  const data = new Map<string, string>();
  return {
    getItem: (k) => data.get(k) ?? null,
    setItem: (k, v) => void data.set(k, v),
    removeItem: (k) => void data.delete(k),
    clear: () => data.clear(),
    key: () => null,
    get length() {
      return data.size;
    },
  };
}

afterEach(() => vi.unstubAllGlobals());

describe("print language preference", () => {
  it("is Bangla on a new device", () => {
    expect(DEFAULT_PRINT_LANGUAGE).toBe("bn");
    expect(parsePrintLanguage(null)).toBe("bn");
  });

  it("ignores anything that is not a saved choice of this version", () => {
    for (const raw of ["{", "[]", '{"v":2,"printLanguage":"en"}', '{"v":1,"printLanguage":"fr"}', '"en"']) {
      expect(parsePrintLanguage(raw)).toBe("bn");
    }
  });

  it("remembers the last choice, and stores nothing else", () => {
    const storage = fakeStorage();
    vi.stubGlobal("window", { localStorage: storage });
    savePrintLanguage("both");
    expect(loadPrintLanguage()).toBe("both");
    expect(JSON.parse(storage.getItem(RX_PREFS_KEY) ?? "")).toEqual({ v: 1, printLanguage: "both" });
    savePrintLanguage("en");
    expect(loadPrintLanguage()).toBe("en");
  });

  it("works when storage is blocked", () => {
    const blocked = {
      get localStorage(): Storage {
        throw new Error("blocked");
      },
    };
    vi.stubGlobal("window", blocked);
    expect(() => savePrintLanguage("en")).not.toThrow();
    expect(loadPrintLanguage()).toBe("bn");
  });
});
