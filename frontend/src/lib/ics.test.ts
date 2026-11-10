import { describe, expect, it } from "vitest";

import { buildIcs, escapeText, foldLine, reminderTitle } from "./ics";

const NOW = new Date(Date.UTC(2026, 10, 10, 6, 0, 0));
const START = new Date(2026, 10, 11);

describe("buildIcs", () => {
  const ics = buildIcs(
    [
      { title: "Seclo 20 mg", time: "08:00" },
      { title: "Seclo 20 mg", time: "20:30" },
    ],
    { now: NOW, start: START, uidPrefix: "t" },
  );
  const lines = ics.split("\r\n");

  it("is a calendar with one daily event per reminder, in floating local time", () => {
    expect(lines[0]).toBe("BEGIN:VCALENDAR");
    expect(lines.filter((l) => l === "BEGIN:VEVENT")).toHaveLength(2);
    expect(lines.filter((l) => l === "RRULE:FREQ=DAILY")).toHaveLength(2);
    expect(lines).toContain("DTSTART:20261111T080000");
    expect(lines).toContain("DTSTART:20261111T203000");
    expect(lines.some((l) => /^DTSTART.*(Z|TZID)/.test(l))).toBe(false); // floating: no zone
    expect(lines).toContain("DTSTAMP:20261110T060000Z");
    expect(lines).toContain("SUMMARY:Seclo 20 mg");
    expect(lines).toContain("UID:t-1@medwise-bd");
  });

  it("uses CRLF line endings and ends with one", () => {
    expect(ics.endsWith("END:VCALENDAR\r\n")).toBe(true);
    expect(ics.replace(/\r\n/g, "")).not.toContain("\n");
  });

  it("has no dose, frequency advice or description beyond the title", () => {
    expect(ics).not.toMatch(/dose|take \d|tablets? a day/i);
  });
});

describe("text helpers", () => {
  it("escapes commas, semicolons, backslashes and newlines", () => {
    expect(escapeText("A, B; C\\D\nE")).toBe("A\\, B\\; C\\\\D\\nE");
  });

  it("folds long lines at 75 octets without splitting Bangla characters", () => {
    const folded = foldLine("SUMMARY:" + "ওষুধের রিমাইন্ডার ".repeat(6));
    const parts = folded.split("\r\n ");
    expect(parts.length).toBeGreaterThan(1);
    for (const part of parts) expect(new TextEncoder().encode(part).length).toBeLessThanOrEqual(75);
    expect(parts.join("")).toBe("SUMMARY:" + "ওষুধের রিমাইন্ডার ".repeat(6));
  });

  it("hides medicine names when asked", () => {
    const m = { brandName: "Seclo", strength: "20 mg" };
    expect(reminderTitle(m, false, "Medicine reminder")).toBe("Seclo 20 mg");
    expect(reminderTitle(m, true, "Medicine reminder")).toBe("Medicine reminder");
  });
});
