/** Picks and monthly totals for a list of medicines; shared by the cost summary and the share page. */

import type { AlternativesResponse, RankedAlternative } from "@/lib/api";
import { monthlyCost, quantityUnit } from "@/lib/savings";

export type Picks = { current: RankedAlternative | null; best: RankedAlternative; cheapest: RankedAlternative };

export function picks(data: AlternativesResponse): Picks | null {
  const [best] = data.alternatives;
  if (!best) return null;
  // Lowest price; on a tie the better-ranked brand (alternatives are already in rank order).
  const cheapest = data.alternatives.reduce((a, b) => (b.price_per_unit < a.price_per_unit ? b : a));
  return { current: data.alternatives.find((a) => a.is_selected) ?? null, best, cheapest };
}

export type PricedRow = { data: AlternativesResponse | null; quantity: number | null };

export type Totals = { current: number | null; best: number; cheapest: number; counted: number };

export function totals(rows: PricedRow[]): Totals {
  const result: Totals = { current: 0, best: 0, cheapest: 0, counted: 0 };
  for (const row of rows) {
    const p = row.data && picks(row.data);
    if (!p || row.quantity === null || !row.data) continue;
    const unit = quantityUnit(row.data.dosage_form);
    result.counted += 1;
    result.best += monthlyCost(p.best.price_per_unit, row.quantity, unit);
    result.cheapest += monthlyCost(p.cheapest.price_per_unit, row.quantity, unit);
    // Without a chosen brand there is no "current" cost for this medicine.
    result.current =
      p.current && result.current !== null
        ? result.current + monthlyCost(p.current.price_per_unit, row.quantity, unit)
        : null;
  }
  return result;
}
