import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { PAGES_CACHE, genericIdFromUrl, offlineUrls, parseSavedAt, titleFromHtml } from "./offline";

describe("offlineUrls", () => {
  it("lists every generic page and every ranking page once", () => {
    const urls = offlineUrls([
      {
        id: 4,
        presentations: [
          { strength: "20 mg", dosage_form: "capsule" },
          { strength: "40 mg", dosage_form: "capsule" },
        ],
      },
      { id: 1, presentations: [{ strength: "120 mg/5 ml", dosage_form: "suspension" }] },
    ]);
    expect(urls).toEqual([
      "/generics/4",
      "/generics/4/ranking?strength=20+mg&form=capsule",
      "/generics/4/ranking?strength=40+mg&form=capsule",
      "/generics/1",
      "/generics/1/ranking?strength=120+mg%2F5+ml&form=suspension",
    ]);
  });
});

describe("titleFromHtml", () => {
  it("drops the site name and decodes entities", () => {
    expect(titleFromHtml("<head><title>Paracetamol · MedWise BD</title></head>")).toBe("Paracetamol");
    expect(titleFromHtml('<title data-x="1">Co-amoxiclav &amp; more · MedWise BD</title>')).toBe(
      "Co-amoxiclav & more",
    );
  });

  it("returns null without a title", () => {
    expect(titleFromHtml("<html></html>")).toBeNull();
    expect(titleFromHtml("<title> </title>")).toBeNull();
  });
});

describe("genericIdFromUrl", () => {
  it("finds generic pages only", () => {
    expect(genericIdFromUrl("https://medwise.example/generics/12")).toBe(12);
    expect(genericIdFromUrl("https://medwise.example/generics/12/ranking?strength=1")).toBeNull();
    expect(genericIdFromUrl("https://medwise.example/alternatives/12")).toBeNull();
  });
});

describe("service worker", () => {
  it("uses the same page cache name as the app", () => {
    const sw = readFileSync(join(__dirname, "../../public/sw.js"), "utf8");
    const version = /const VERSION = "([^"]+)"/.exec(sw)?.[1];
    expect(`medwise-pages-${version}`).toBe(PAGES_CACHE);
  });
});

describe("parseSavedAt", () => {
  it("reads the time a page was saved", () => {
    expect(parseSavedAt("2026-11-10T08:30:00.000Z")?.toISOString()).toBe("2026-11-10T08:30:00.000Z");
    expect(parseSavedAt(null)).toBeNull();
    expect(parseSavedAt("not a date")).toBeNull();
  });
});
