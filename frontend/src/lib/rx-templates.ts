/**
 * Doctor templates (R5): pad lines <-> saved template lines, and applying a template.
 *
 * A template holds only medicine lines (brand code with a name snapshot, generic + strength + form,
 * or a free-text name; pattern, unit, food, duration, substitution, the doctor's note), tests and
 * advice. Nothing here ever touches the patient fields of the pad.
 */

import type { components } from "./api-schema";
import type { BrandIndexItem } from "./brand-index";
import { MAX_FREE_NAME, MAX_LINES, formWordFor, newLine, type RxLine, type RxSource } from "./rx";
import { durationCode, parseDuration } from "./rx-payload";

export type TemplateLine = components["schemas"]["TemplateLine"];
export type TemplateLineOut = components["schemas"]["TemplateLineOut"];

/** The pad's lines as template lines (a name snapshot is kept with each brand code). */
export function toTemplateLines(lines: RxLine[]): TemplateLine[] {
  return lines.map((line) => {
    const common = {
      form_word: line.formWord.slice(0, 12),
      pattern: line.pattern.slice(0, 40),
      unit: line.unit,
      food: line.food,
      duration: durationCode(line.duration),
      note: line.note.slice(0, 120),
    };
    const s = line.source;
    if (s.kind === "brand") {
      return {
        kind: "brand",
        code: s.code,
        name: s.name,
        generic: s.generic,
        strength: s.strength,
        dosage_form: s.dosageForm,
        substitution: line.substitution,
        ...common,
      };
    }
    if (s.kind === "generic") {
      return {
        kind: "generic",
        name: s.generic,
        generic: s.generic,
        strength: s.strength,
        dosage_form: s.dosageForm,
        substitution: false,
        ...common,
      };
    }
    return { kind: "free", name: s.name, generic: "", strength: "", dosage_form: "", substitution: false, ...common };
  });
}

export type Catalog = {
  brands: Map<string, BrandIndexItem>;
  generics: Map<string, number>; // generic name -> id
};

/** A saved template line as a pad line, looked up in today's catalog. */
export function fromTemplateLine(line: TemplateLineOut, catalog: Catalog, id: string): { line: RxLine; asWritten: boolean } {
  let source: RxSource | null = null;
  if (line.kind === "brand" && line.code) {
    const b = catalog.brands.get(line.code);
    if (b) {
      source = {
        kind: "brand",
        code: b.code,
        name: b.name,
        genericId: b.generic_id,
        generic: b.generic,
        strength: b.strength,
        dosageForm: b.dosage_form,
        manufacturer: b.manufacturer,
        pricePerUnit: b.price_per_unit,
        priceCheckedOn: b.price_checked_on ?? null,
        rank: b.rank,
        groupSize: b.group_size,
        approvals: b.approvals,
      };
    }
  } else if (line.kind === "generic") {
    const genericId = catalog.generics.get(line.generic ?? "");
    if (genericId !== undefined && line.strength && line.dosage_form) {
      source = { kind: "generic", genericId, generic: line.generic ?? "", strength: line.strength, dosageForm: line.dosage_form };
    }
  }
  // Not (or no longer) in MedWise: kept as written, like any free-text line.
  const asWritten = source === null && line.kind !== "free";
  if (!source) {
    const written = [line.name, line.kind === "generic" ? line.strength : ""].filter(Boolean).join(" ");
    source = { kind: "free", name: written.slice(0, MAX_FREE_NAME) };
  }
  const form = source.kind === "free" ? line.dosage_form : source.dosageForm;
  let duration: RxLine["duration"];
  try {
    duration = parseDuration(line.duration ?? "");
  } catch {
    duration = { kind: "none" };
  }
  return {
    line: {
      ...newLine(source, id),
      formWord: line.form_word || formWordFor(form),
      pattern: line.pattern ?? "",
      unit: line.unit ?? "tablet",
      food: line.food ?? "",
      duration,
      note: line.note ?? "",
      substitution: source.kind === "brand" && Boolean(line.substitution),
    },
    asWritten: asWritten || Boolean(line.gone),
  };
}

/** Adds a template's lines after the pad's (up to 12 in all). */
export function applyLines(current: RxLine[], incoming: RxLine[], max = MAX_LINES): { lines: RxLine[]; skipped: number } {
  const room = Math.max(0, max - current.length);
  return { lines: [...current, ...incoming.slice(0, room)], skipped: Math.max(0, incoming.length - room) };
}

/** Template text goes after what is already in the box (on a new line). */
export function appendText(existing: string, added: string): string {
  if (!added.trim()) return existing;
  if (!existing.trim()) return added;
  return `${existing.trimEnd()}\n${added}`;
}
