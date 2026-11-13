/**
 * The public brand index (GET /api/brands/index): every brand with its stable code. Used on the
 * device to migrate lists saved before brand codes existed, without asking the server about any
 * particular medicine.
 */
import type { components } from "./api-schema";

export type BrandIndexItem = components["schemas"]["BrandIndexItem"];

const norm = (s: string) => s.trim().replace(/\s+/g, " ").toLowerCase();

/**
 * The code of a brand saved before codes existed. The brand's own details decide (database ids may
 * have changed since it was saved); the old id only breaks a tie or helps when names drifted, and
 * only if its details still agree. Null when the brand is no longer listed.
 */
export function findBrandCode(
  index: BrandIndexItem[],
  saved: { id?: number; brandName: string; strength: string; dosageForm: string; genericName?: string },
): string | null {
  const same = index.filter(
    (b) =>
      norm(b.name) === norm(saved.brandName) &&
      norm(b.strength) === norm(saved.strength) &&
      norm(b.dosage_form) === norm(saved.dosageForm),
  );
  if (same.length === 1) return same[0].code;
  const byId = index.find((b) => b.id === saved.id);
  if (same.length > 1) return (same.find((b) => b.id === saved.id) ?? same[0]).code;
  if (
    byId &&
    norm(byId.strength) === norm(saved.strength) &&
    norm(byId.dosage_form) === norm(saved.dosageForm) &&
    (!saved.genericName || norm(byId.generic) === norm(saved.genericName))
  ) {
    return byId.code;
  }
  return null;
}
