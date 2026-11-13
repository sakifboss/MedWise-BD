/** Monthly cost and savings maths. The quantity always comes from the user's prescription. */

export const DAYS_PER_MONTH = 30;

/** URL query parameter that carries the quantity, e.g. ?per=2. */
export const QUANTITY_PARAM = "per";

export type QuantityUnit = {
  /** Dosage form the quantity counts (tablet, capsule, suspension, eye drops). */
  form: string;
  /** How many entered quantities make up one month. */
  perMonth: number;
  step: number;
  max: number;
};

/** Forms priced per bottle (Arogga MRP of one bottle), not per tablet or capsule. */
const PER_BOTTLE_FORMS: ReadonlySet<string> = new Set(["suspension", "eye drops"]);

export function isPerBottle(dosageForm: string): boolean {
  return PER_BOTTLE_FORMS.has(dosageForm);
}

/** Bottled forms are priced per bottle, so the user enters bottles a month. */
export function quantityUnit(dosageForm: string): QuantityUnit {
  if (isPerBottle(dosageForm)) {
    return { form: dosageForm, perMonth: 1, step: 1, max: 20 };
  }
  return { form: dosageForm, perMonth: DAYS_PER_MONTH, step: 0.5, max: 24 };
}

/** Returns the quantity if it is a usable positive number for this unit, else null. */
export function parseQuantity(raw: string | null, unit: QuantityUnit): number | null {
  if (raw === null || raw.trim() === "") return null;
  const value = Number(raw);
  if (!Number.isFinite(value) || value <= 0 || value > unit.max) return null;
  return value;
}

export function monthlyCost(pricePerUnit: number, quantity: number, unit: QuantityUnit): number {
  return pricePerUnit * quantity * unit.perMonth;
}

/** Positive when the alternative is cheaper than the current medicine. */
export function monthlySaving(currentMonthly: number, alternativeMonthly: number): number {
  return currentMonthly - alternativeMonthly;
}
