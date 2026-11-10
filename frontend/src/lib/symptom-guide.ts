/**
 * Symptom guide helpers (pure, unit-tested). The guide never diagnoses and never names a disease
 * or a medicine; these helpers only arrange the NHS checklist and the person's own note.
 */
import type { components } from "./api-schema";
import type { SavedMedicine } from "./my-medicines";

export type RedFlag = components["schemas"]["RedFlagOut"];
export type SymptomSetup = components["schemas"]["SymptomGuideSetup"];
export type SymptomAnswers = components["schemas"]["SymptomGuideIn"];
export type SymptomResult = components["schemas"]["SymptomGuideOut"];
export type DoctorNote = components["schemas"]["DoctorNote"];

export const TEXT_MAX = 1000;

/** Checklist groups in the order the data gives them, each with its items and source pages. */
export function groupFlags(flags: RedFlag[]): { group: string; items: RedFlag[]; sources: string[] }[] {
  const groups = new Map<string, RedFlag[]>();
  for (const flag of flags) groups.set(flag.group, [...(groups.get(flag.group) ?? []), flag]);
  return [...groups].map(([group, items]) => ({
    group,
    items,
    sources: [...new Set(items.map((i) => i.source_url))],
  }));
}

/** Children never get the pregnancy question; a hidden answer is sent as "not applicable". */
export function effectivePregnant(
  ageGroup: SymptomAnswers["age_group"] | null,
  pregnant: SymptomAnswers["pregnant"] | null,
): SymptomAnswers["pregnant"] | null {
  return ageGroup === "child" ? "not_applicable" : pregnant;
}

/** The answers ready to send, or null while something is missing. */
export function readyAnswers(form: {
  text: string;
  since: SymptomAnswers["since"] | null;
  severity: SymptomAnswers["severity"] | null;
  age_group: SymptomAnswers["age_group"] | null;
  pregnant: SymptomAnswers["pregnant"] | null;
  lang: SymptomAnswers["lang"];
}): SymptomAnswers | null {
  const text = form.text.replace(/\s+/g, " ").trim();
  const pregnant = effectivePregnant(form.age_group, form.pregnant);
  if (text.length < 3 || text.length > TEXT_MAX || !form.since || !form.severity || !form.age_group || !pregnant) {
    return null;
  }
  return { text, since: form.since, severity: form.severity, age_group: form.age_group, pregnant, lang: form.lang };
}

/** "a\n\n b \n" -> ["a", "b"]: the other-symptoms box holds one per line. */
export function lines(value: string): string[] {
  return value
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);
}

export type NoteLabels = {
  heading: string;
  mainProblem: string;
  duration: string;
  howBad: string;
  ageGroup: string;
  pregnancy: string;
  otherSymptoms: string;
  medicines: string;
  perDay: (n: string) => string;
  severity: Record<SymptomAnswers["severity"], string>;
  age: Record<SymptomAnswers["age_group"], string>;
  pregnant: Record<SymptomAnswers["pregnant"], string>;
};

/**
 * The note as plain text for sharing and printing: what the person told us (after their own
 * edits), plus their saved medicines only if they chose to include them.
 */
export function noteText(
  note: DoctorNote,
  answers: Pick<SymptomAnswers, "severity" | "age_group" | "pregnant">,
  medicines: SavedMedicine[],
  labels: NoteLabels,
): string {
  const out = [labels.heading, "", `${labels.mainProblem}: ${note.main_problem.trim()}`];
  if (note.duration.trim()) out.push(`${labels.duration}: ${note.duration.trim()}`);
  out.push(`${labels.howBad}: ${labels.severity[answers.severity]}`);
  out.push(`${labels.ageGroup}: ${labels.age[answers.age_group]}`);
  if (answers.pregnant !== "not_applicable") out.push(`${labels.pregnancy}: ${labels.pregnant[answers.pregnant]}`);
  const others = note.other_symptoms.map((s) => s.trim()).filter(Boolean);
  if (others.length) out.push(`${labels.otherSymptoms}: ${others.join("; ")}`);
  if (medicines.length) {
    out.push("", `${labels.medicines}:`);
    for (const m of medicines) {
      const amount = m.unitsPerDay ? ` (${labels.perDay(String(m.unitsPerDay))})` : "";
      out.push(`- ${m.brandName} ${m.strength} ${m.dosageForm}${amount}`);
    }
  }
  return out.join("\n");
}
