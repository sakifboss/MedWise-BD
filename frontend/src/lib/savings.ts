/** Monthly cost and savings maths. The quantity always comes from the user's prescription. */

export const DAYS_PER_MONTH = 30;

export type QuantityUnit = {
  /** What the user enters, e.g. "tablets a day". */
  label: string;
  /** How many entered quantities make up one month. */
  perMonth: number;
  step: number;
  max: number;
};

/** Suspensions are priced per bottle, so the user enters bottles a month. */
export function quantityUnit(dosageForm: string): QuantityUnit {
  if (dosageForm === "suspension") {
    return { label: "bottles a month", perMonth: 1, step: 1, max: 20 };
  }
  return { label: `${dosageForm}s a day`, perMonth: DAYS_PER_MONTH, step: 0.5, max: 24 };
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

export function formatTaka(value: number): string {
  return `Tk ${Math.round(value).toLocaleString("en-US")}`;
}
