import type { Dict } from "@/i18n/dictionaries";
import type { MatchOption } from "@/lib/api";

export const NONE = "none";

/** One medicine on the confirmation screen. `choice` is an option index as a string, or NONE. */
export type DraftItem = {
  key: string;
  extractedName: string;
  extractedStrength: string | null;
  options: MatchOption[];
  choice: string;
};

export function optionLabel(option: MatchOption, t: Dict): string {
  return `${option.name} ${option.strength} ${t.fmt.form(option.dosage_form)}`;
}

export function optionKey(option: MatchOption): string {
  return option.kind === "brand"
    ? `b${option.brand_id}`
    : `g${option.generic_id}-${option.strength}-${option.dosage_form}`;
}
