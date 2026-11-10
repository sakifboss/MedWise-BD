import { describe, expect, it } from "vitest";

import { DICTIONARIES } from "@/i18n/dictionaries";

import type { SavedMedicine } from "./my-medicines";
import { effectivePregnant, groupFlags, lines, noteText, readyAnswers, type RedFlag } from "./symptom-guide";

const flag = (id: string, group: string, url = "https://www.nhs.uk/a/"): RedFlag => ({
  id,
  group,
  text: id,
  source_url: url,
});

describe("checklist", () => {
  it("groups signs in data order and lists each group's sources once", () => {
    const groups = groupFlags([
      flag("c1", "chest"),
      flag("b1", "breathing"),
      flag("c2", "chest"),
      flag("k1", "child_under_5", "https://www.nhs.uk/a/"),
      flag("k2", "child_under_5", "https://www.nhs.uk/b/"),
    ]);
    expect(groups.map((g) => [g.group, g.items.map((i) => i.id)])).toEqual([
      ["chest", ["c1", "c2"]],
      ["breathing", ["b1"]],
      ["child_under_5", ["k1", "k2"]],
    ]);
    expect(groups[2].sources).toEqual(["https://www.nhs.uk/a/", "https://www.nhs.uk/b/"]);
  });

  it("has a title in both languages for every group in the data", async () => {
    const { readFileSync } = await import("node:fs");
    const seed = JSON.parse(readFileSync("../data/seed/red_flags.json", "utf-8")) as { records: RedFlag[] };
    for (const g of groupFlags(seed.records)) {
      expect(DICTIONARIES.en.symptoms.groups).toHaveProperty(g.group);
      expect(DICTIONARIES.bn.symptoms.groups).toHaveProperty(g.group);
    }
  });
});

describe("answers", () => {
  const form = {
    text: "  Itchy   rash on arms ",
    since: "weeks" as const,
    severity: "mild" as const,
    age_group: "adult" as const,
    pregnant: "no" as const,
    lang: "en" as const,
  };

  it("are ready only when every question is answered", () => {
    expect(readyAnswers(form)).toEqual({ ...form, text: "Itchy rash on arms" });
    expect(readyAnswers({ ...form, since: null })).toBeNull();
    expect(readyAnswers({ ...form, text: "ab" })).toBeNull();
    expect(readyAnswers({ ...form, text: "x".repeat(1001) })).toBeNull();
    expect(readyAnswers({ ...form, pregnant: null })).toBeNull();
  });

  it("never ask a child about pregnancy", () => {
    expect(effectivePregnant("child", "yes")).toBe("not_applicable");
    expect(readyAnswers({ ...form, age_group: "child", pregnant: null })?.pregnant).toBe("not_applicable");
    expect(effectivePregnant("adult", "yes")).toBe("yes");
  });

  it("split other symptoms one per line", () => {
    expect(lines("a\n\n  b \r\nc")).toEqual(["a", "b", "c"]);
  });
});

describe("noteText", () => {
  const t = DICTIONARIES.en.symptoms;
  const labels = t.noteLabels;
  const note = { main_problem: "Itchy rash on both arms", duration: "1 to 4 weeks", other_symptoms: ["Dry skin", " "] };
  const seclo: SavedMedicine = {
    brandId: 22,
    brandName: "Seclo",
    genericId: 4,
    genericName: "Omeprazole",
    strength: "20 mg",
    dosageForm: "capsule",
    unitsPerDay: 2,
    reminderTimes: [],
    addedOn: "2026-11-01",
  };

  it("holds the answers, and no medicines unless chosen", () => {
    const text = noteText(note, { severity: "mild", age_group: "adult", pregnant: "no" }, [], labels);
    expect(text.split("\n")).toEqual([
      "Note for the doctor – written from my answers, not a diagnosis",
      "",
      "Main problem: Itchy rash on both arms",
      "Since: 1 to 4 weeks",
      "How bad: Mild",
      "Age group: Adult",
      "Pregnant: No",
      "Other symptoms: Dry skin",
    ]);
  });

  it("adds saved medicines only when given, and leaves out pregnancy when not applicable", () => {
    const text = noteText(note, { severity: "severe", age_group: "child", pregnant: "not_applicable" }, [seclo], labels);
    expect(text).toContain("My medicines:\n- Seclo 20 mg capsule (2 a day)");
    expect(text).not.toContain("Pregnant");
  });

  it("works in Bangla", () => {
    const text = noteText(note, { severity: "moderate", age_group: "older_adult", pregnant: "no" }, [], DICTIONARIES.bn.symptoms.noteLabels);
    expect(text).toContain("কতটা গুরুতর: মাঝারি");
    expect(text.startsWith("ডাক্তারের জন্য নোট")).toBe(true);
  });
});
