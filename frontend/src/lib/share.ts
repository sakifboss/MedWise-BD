/**
 * Share links for a list of medicines. Everything is in the URL (no data is stored):
 *   /share?m=c:BR00042:2&m=g:12:500 mg:tablet:
 * "c:<brand code>:<quantity>" or "g:<generic id>:<strength>:<dosage form>:<quantity>";
 * the quantity is optional and always comes from the user's prescription. Links made before brand
 * codes existed ("b:<brand id>:<quantity>") still open.
 */

import type { MatchOption } from "@/lib/api";

export const SHARE_PATH = "/share";
export const SHARE_PARAM = "m";
export const MAX_SHARE_ITEMS = 10;
/** Upper bound for any quantity in a link; the page re-checks it per dosage form. */
const MAX_QUANTITY = 24;
const CODE = /^BR\d{5}$/;

export type ShareItem =
  /** `ref` is the brand code, or the database id from an old link. */
  | { kind: "brand"; ref: string; quantity: number | null }
  | { kind: "generic"; genericId: number; strength: string; dosageForm: string; quantity: number | null };

export function shareItem(option: MatchOption, quantity: number | null): ShareItem {
  const ref = option.brand_code ?? (option.brand_id != null ? String(option.brand_id) : null);
  return option.kind === "brand" && ref !== null
    ? { kind: "brand", ref, quantity }
    : {
        kind: "generic",
        genericId: option.generic_id,
        strength: option.strength,
        dosageForm: option.dosage_form,
        quantity,
      };
}

function encode(item: ShareItem): string {
  const q = item.quantity ?? "";
  if (item.kind === "brand") return CODE.test(item.ref) ? `c:${item.ref}:${q}` : `b:${item.ref}:${q}`;
  return `g:${item.genericId}:${item.strength}:${item.dosageForm}:${q}`;
}

export function shareHref(items: ShareItem[]): string {
  const params = new URLSearchParams();
  for (const item of items.slice(0, MAX_SHARE_ITEMS)) params.append(SHARE_PARAM, encode(item));
  return `${SHARE_PATH}?${params}`;
}

function id(value: string | undefined): number | null {
  return value && /^\d+$/.test(value) && Number(value) > 0 ? Number(value) : null;
}

function quantity(value: string | undefined): number | null {
  if (!value) return null;
  const n = Number(value);
  return Number.isFinite(n) && n > 0 && n <= MAX_QUANTITY ? n : null;
}

function decode(value: string): ShareItem | null {
  const parts = value.split(":");
  if (parts[0] === "c" && parts.length === 3) {
    const code = parts[1].toUpperCase();
    return CODE.test(code) ? { kind: "brand", ref: code, quantity: quantity(parts[2]) } : null;
  }
  if (parts[0] === "b" && parts.length === 3) {
    const brandId = id(parts[1]);
    return brandId === null ? null : { kind: "brand", ref: String(brandId), quantity: quantity(parts[2]) };
  }
  if (parts[0] === "g" && parts.length === 5) {
    const genericId = id(parts[1]);
    const [strength, dosageForm] = [parts[2].trim(), parts[3].trim()];
    if (genericId === null || !strength || !dosageForm) return null;
    return { kind: "generic", genericId, strength, dosageForm, quantity: quantity(parts[4]) };
  }
  return null;
}

/** Reads the `m` query values; malformed entries are skipped, duplicates and extras dropped. */
export function parseShareItems(values: string | string[] | undefined): ShareItem[] {
  const seen = new Set<string>();
  const items: ShareItem[] = [];
  for (const value of [values ?? []].flat()) {
    const item = decode(value);
    if (!item) continue;
    const key = encode({ ...item, quantity: null });
    if (seen.has(key)) continue;
    seen.add(key);
    items.push(item);
    if (items.length === MAX_SHARE_ITEMS) break;
  }
  return items;
}
