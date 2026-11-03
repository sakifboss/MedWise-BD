export function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** Parses a positive integer route segment; returns null for anything else. */
export function parseId(value: string): number | null {
  return /^\d+$/.test(value) && Number(value) > 0 ? Number(value) : null;
}

export function rankingHref(genericId: number, strength: string, dosageForm: string): string {
  const params = new URLSearchParams({ strength, form: dosageForm });
  return `/generics/${genericId}/ranking?${params}`;
}
