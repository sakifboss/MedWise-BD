/**
 * The Rx Pad's prescription lines and the patient instruction made from them (R3).
 *
 * Everything here works only on what the doctor typed or picked. Nothing suggests a medicine,
 * dose, frequency or duration, and nothing here is ever stored or sent anywhere: the lines live
 * only in the open browser tab and on the printed page.
 */

export const MAX_LINES = 12;
export const MAX_FREE_NAME = 40;

export type FoodTiming = "" | "before" | "after" | "with" | "any";
export type DurationUnit = "days" | "weeks" | "months";
export type Duration = { kind: "none" } | { kind: "continue" } | { kind: "fixed"; n: number; unit: DurationUnit };
export const RX_UNITS = ["tablet", "capsule", "spoon", "ml", "drop", "puff", "application"] as const;
export type RxUnit = (typeof RX_UNITS)[number];
export type InstructionLang = "bn" | "en";

export type RxSource =
  | {
      kind: "brand";
      code: string;
      name: string;
      genericId: number;
      generic: string;
      strength: string;
      dosageForm: string;
      manufacturer: string;
      pricePerUnit: number;
      priceCheckedOn: string | null;
      rank: number;
      groupSize: number;
      approvals: number;
    }
  | { kind: "generic"; genericId: number; generic: string; strength: string; dosageForm: string }
  | { kind: "free"; name: string };

export type RxLine = {
  id: string;
  source: RxSource;
  formWord: string;
  /** As typed: "1+0+1", "½+0+½+0", or free text such as "as needed". */
  pattern: string;
  unit: RxUnit;
  food: FoodTiming;
  duration: Duration;
  note: string;
  /** Checked: another brand of the same generic, strength and form may be given. */
  substitution: boolean;
};

/** The same for every line, none pre-selected (the app never proposes a dose). */
export const PATTERN_SHORTCUTS = ["1+0+1", "1+1+1", "0+0+1", "1+0+0", "1+1+1+1"] as const;

const FORM_WORDS: Record<string, string> = {
  tablet: "Tab.",
  capsule: "Cap.",
  suspension: "Susp.",
  syrup: "Syp.",
  injection: "Inj.",
  "eye drops": "Drop",
  "ear drops": "Drop",
  "eye ointment": "Oint.",
  ointment: "Oint.",
  cream: "Cream",
  gel: "Gel",
  mouthwash: "Mouthwash",
  inhaler: "Inhaler",
};

/** The word printed before the medicine name (the doctor can change it). */
export function formWordFor(dosageForm: string | null | undefined): string {
  if (!dosageForm) return "";
  return FORM_WORDS[dosageForm] ?? dosageForm.charAt(0).toUpperCase() + dosageForm.slice(1);
}

/** The unit a dose counts, from the dosage form (the doctor can change it). */
export function unitFor(dosageForm: string | null | undefined): RxUnit {
  switch (dosageForm) {
    case "capsule":
      return "capsule";
    case "suspension":
    case "syrup":
      return "spoon";
    case "eye drops":
    case "ear drops":
      return "drop";
    case "cream":
    case "ointment":
    case "eye ointment":
    case "gel":
      return "application";
    case "inhaler":
      return "puff";
    default:
      return "tablet";
  }
}

// ---------------------------------------------------------------- dose patterns

const BANGLA_DIGITS = "০১২৩৪৫৬৭৮৯";

function latinDigits(text: string): string {
  return text.replace(/[০-৯]/g, (d) => String(BANGLA_DIGITS.indexOf(d)));
}

function parseAmount(token: string): number | null {
  const t = latinDigits(token.trim());
  const match = /^(\d{0,2})(½)?$/.exec(t);
  if (!match || (!match[1] && !match[2])) return null;
  const value = (match[1] ? Number(match[1]) : 0) + (match[2] ? 0.5 : 0);
  return value <= 20 ? value : null;
}

/** "1+0+1" -> [1, 0, 1]; "½+½+1+0" -> [0.5, 0.5, 1, 0]; anything else (free text) -> null. */
export function parsePattern(pattern: string): number[] | null {
  const parts = pattern.split("+");
  if (parts.length !== 3 && parts.length !== 4) return null;
  const amounts = parts.map(parseAmount);
  return amounts.every((a): a is number => a !== null) ? amounts : null;
}

// ---------------------------------------------------------------- numbers

/** 1.5 -> "1½" (bn "১½"), 0.5 -> "½", 30 -> "30" (bn "৩০"). */
export function amountText(value: number, lang: InstructionLang): string {
  const whole = Math.floor(value);
  const half = value - whole >= 0.5 ? "½" : "";
  if (whole === 0 && half) return half;
  const digits = lang === "bn" ? whole.toLocaleString("bn-BD") : String(whole);
  return digits + half;
}

export function durationDays(duration: Duration): number | null {
  if (duration.kind !== "fixed") return null;
  return duration.n * (duration.unit === "weeks" ? 7 : duration.unit === "months" ? 30 : 1);
}

/** Tablets or capsules for the whole course; null when not countable (free text, no fixed duration). */
export function totalUnits(line: Pick<RxLine, "pattern" | "unit" | "duration">): number | null {
  if (line.unit !== "tablet" && line.unit !== "capsule") return null;
  const slots = parsePattern(line.pattern);
  const days = durationDays(line.duration);
  if (!slots || days === null) return null;
  const total = slots.reduce((a, b) => a + b, 0) * days;
  return total > 0 ? total : null;
}

/** Approximate cost (total x Arogga MRP per unit), only for catalog brands with a total. */
export function estimatedCost(line: RxLine): number | null {
  const total = totalUnits(line);
  if (total === null || line.source.kind !== "brand") return null;
  return Math.round(total * line.source.pricePerUnit * 100) / 100;
}

// ---------------------------------------------------------------- the patient instruction

const SLOTS = {
  en: ["in the morning", "at noon", "at night"],
  bn: ["সকালে", "দুপুরে", "রাতে"],
};

const FOOD = {
  en: { before: "before food", after: "after food", with: "with food", any: "with or without food" },
  bn: { before: "খাবারের আগে", after: "খাবারের পরে", with: "খাবারের সাথে", any: "খাবারের আগে বা পরে" },
};

function enUnit(unit: RxUnit, amount: number): string {
  const plural = amount > 1;
  switch (unit) {
    case "tablet":
    case "capsule":
      return "";
    case "spoon":
      return plural ? " spoons" : " spoon";
    case "ml":
      return " ml";
    case "drop":
      return plural ? " drops" : " drop";
    case "puff":
      return plural ? " puffs" : " puff";
    case "application":
      return plural ? " applications" : " application";
  }
}

const BN_UNIT: Record<RxUnit, string> = {
  tablet: "টি",
  capsule: "টি",
  spoon: " চামচ",
  ml: " মি.লি.",
  drop: " ফোঁটা",
  puff: " পাফ",
  application: " বার",
};

function dose(amount: number, unit: RxUnit, lang: InstructionLang): string {
  const text = amountText(amount, lang);
  return lang === "bn" ? text + BN_UNIT[unit] : text + enUnit(unit, amount);
}

function joinEn(parts: string[]): string {
  return parts.length < 2 ? parts.join("") : `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}`;
}

function dosePart(line: Pick<RxLine, "pattern" | "unit">, lang: InstructionLang): string {
  const slots = parsePattern(line.pattern);
  if (!slots) return line.pattern.trim(); // free text, as the doctor wrote it
  const taken = slots.filter((a) => a > 0);
  if (!taken.length) return "";
  if (slots.length === 3) {
    const parts = slots.flatMap((amount, i) => {
      if (amount <= 0) return [];
      const d = dose(amount, line.unit, lang);
      return [lang === "bn" ? `${SLOTS.bn[i]} ${d}` : `${d} ${SLOTS.en[i]}`];
    });
    return lang === "bn" ? parts.join(" ও ") : joinEn(parts);
  }
  // Four slots: "4 times a day" with the amounts.
  const times = taken.length;
  const same = taken.every((a) => a === taken[0]);
  if (lang === "bn") {
    const head = `দিনে ${times.toLocaleString("bn-BD")} বার`;
    return same ? `${head}, প্রতিবার ${dose(taken[0], line.unit, "bn")}` : `${head} (${slots.map((a) => amountText(a, "bn")).join(" + ")})`;
  }
  const head = `${times} ${times === 1 ? "time" : "times"} a day`;
  return same ? `${dose(taken[0], line.unit, "en")}, ${head}` : `${head} (${slots.map((a) => amountText(a, "en")).join(" + ")})`;
}

function durationText(duration: Duration, lang: InstructionLang): string {
  if (duration.kind === "none") return "";
  if (duration.kind === "continue") return lang === "bn" ? "চলবে" : "continue";
  const n = lang === "bn" ? duration.n.toLocaleString("bn-BD") : String(duration.n);
  if (lang === "bn") return `${n} ${{ days: "দিন", weeks: "সপ্তাহ", months: "মাস" }[duration.unit]}`;
  const one = duration.n === 1;
  return `${n} ${{ days: one ? "day" : "days", weeks: one ? "week" : "weeks", months: one ? "month" : "months" }[duration.unit]}`;
}

/**
 * The sentence for the patient, made only from the doctor's input. Examples:
 * 0+0+1, tablet, after food, 30 days -> "1 at night, after food — 30 days (30 in total)"
 *                                       "রাতে ১টি, খাবারের পরে — ৩০ দিন (মোট ৩০টি)"
 */
export function instruction(line: Pick<RxLine, "pattern" | "unit" | "food" | "duration">, lang: InstructionLang): string {
  const head = [dosePart(line, lang), line.food ? FOOD[lang][line.food] : ""].filter(Boolean).join(", ");
  const length = durationText(line.duration, lang);
  const total = totalUnits(line);
  const totalText =
    total === null ? "" : lang === "bn" ? ` (মোট ${amountText(total, "bn")}টি)` : ` (${amountText(total, "en")} in total)`;
  if (!length) return head;
  return head ? `${head} — ${length}${totalText}` : `${length}${totalText}`;
}

// ---------------------------------------------------------------- checks across lines

export function genericIdOf(source: RxSource): number | null {
  return source.kind === "free" ? null : source.genericId;
}

/** Generics that appear on more than one line (information for the doctor, never blocking). */
export function duplicateGenerics(lines: RxLine[]): { genericId: number; generic: string; count: number }[] {
  const seen = new Map<number, { generic: string; count: number }>();
  for (const line of lines) {
    if (line.source.kind === "free") continue;
    const entry = seen.get(line.source.genericId) ?? { generic: line.source.generic, count: 0 };
    entry.count += 1;
    seen.set(line.source.genericId, entry);
  }
  return [...seen.entries()].filter(([, e]) => e.count > 1).map(([genericId, e]) => ({ genericId, ...e }));
}

/** Distinct catalog generic ids, for the interaction check (the only thing that call sends). */
export function catalogGenericIds(lines: RxLine[]): number[] {
  return [...new Set(lines.map((l) => genericIdOf(l.source)).filter((id): id is number => id !== null))].sort(
    (a, b) => a - b,
  );
}

/** A new line for a picked medicine: form word and unit from its dosage form; no dose. */
export function newLine(source: RxSource, id: string): RxLine {
  const form = source.kind === "free" ? null : source.dosageForm;
  return {
    id,
    source,
    formWord: formWordFor(form),
    pattern: "",
    unit: unitFor(form),
    food: "",
    duration: { kind: "none" },
    note: "",
    substitution: false,
  };
}
