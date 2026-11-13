/**
 * "My Medicines": a list kept only on this device (localStorage). Nothing about it is sent to
 * the MedWise BD backend; pages only call the public ranking, brand index and interaction APIs.
 *
 * Format version 2 refers to brands by their stable code (BR00042), because database ids change
 * when the seed data is re-imported. A version 1 list (by id) is migrated on the device with the
 * public brand index: each item is matched by its own details (brand, strength, form), with the
 * old id only as a fallback; an item that cannot be matched is kept, marked as no longer listed.
 *
 * Pure helpers first (unit-tested), then the browser-only storage parts.
 */
import type { AlternativesResponse, RankedAlternative } from "@/lib/api";
import { findBrandCode, type BrandIndexItem } from "@/lib/brand-index";

export const STORAGE_KEY = "medwise.myMedicines";
export const FORMAT_VERSION = 2;
const MAX_ITEMS = 50;
const MAX_TIMES = 6;
const TIME = /^([01]\d|2[0-3]):[0-5]\d$/;
const DATE = /^\d{4}-\d{2}-\d{2}$/;
const CODE = /^BR\d{5}$/;

/** One saved medicine: what the brand is, and only what the user typed (never a suggestion). */
export type SavedMedicine = {
  /** Stable brand code; null when the brand is no longer in MedWise (kept so nothing is lost). */
  brandCode: string | null;
  brandName: string;
  genericName: string;
  strength: string;
  dosageForm: string;
  /** How many units a day the prescription says, as the user entered it; null when not given. */
  unitsPerDay: number | null;
  /** Reminder times the user chose, "HH:MM", sorted; the app never suggests times. */
  reminderTimes: string[];
  /** Day it was first saved, "YYYY-MM-DD". */
  addedOn: string;
};

/** A version 1 item (by database id), waiting to be matched to a brand code. */
export type LegacyMedicine = Omit<SavedMedicine, "brandCode"> & { brandId: number };

export type MyMedicinesList = {
  version: typeof FORMAT_VERSION;
  items: SavedMedicine[];
  /** Version 1 items not migrated yet (the brand index was not available). */
  legacy?: LegacyMedicine[];
};

export const EMPTY_LIST: MyMedicinesList = { version: FORMAT_VERSION, items: [] };

/** Identity of a saved medicine: its code, or its details when it is no longer listed. */
export function itemKey(m: Pick<SavedMedicine, "brandCode" | "brandName" | "strength" | "dosageForm">): string {
  return m.brandCode ?? `name:${m.brandName}|${m.strength}|${m.dosageForm}`.toLowerCase();
}

// ---------------------------------------------------------------- validation and migration

function text(value: unknown, max = 120): string | null {
  return typeof value === "string" && value.trim() && value.length <= max ? value.trim() : null;
}

function positiveInt(value: unknown): number | null {
  return typeof value === "number" && Number.isInteger(value) && value > 0 ? value : null;
}

function units(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) && value > 0 && value <= 50 ? value : null;
}

export function cleanTimes(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  const times = value.filter((v): v is string => typeof v === "string" && TIME.test(v));
  return [...new Set(times)].sort().slice(0, MAX_TIMES);
}

function common(r: Record<string, unknown>) {
  const brandName = text(r.brandName);
  const genericName = text(r.genericName);
  const strength = text(r.strength, 50);
  const dosageForm = text(r.dosageForm, 50);
  if (!brandName || !genericName || !strength || !dosageForm) return null;
  return {
    brandName,
    genericName,
    strength,
    dosageForm,
    unitsPerDay: units(r.unitsPerDay),
    reminderTimes: cleanTimes(r.reminderTimes),
    addedOn: typeof r.addedOn === "string" && DATE.test(r.addedOn) ? r.addedOn : today(),
  };
}

/** A valid version 2 item from unknown data, or null. Unknown fields are dropped. */
export function toSavedMedicine(raw: unknown): SavedMedicine | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  const rest = common(r);
  if (!rest) return null;
  const brandCode = typeof r.brandCode === "string" && CODE.test(r.brandCode) ? r.brandCode : null;
  if (brandCode === null && r.brandCode !== null) return null;
  return { brandCode, ...rest };
}

function toLegacy(raw: unknown): LegacyMedicine | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  const brandId = positiveInt(r.brandId);
  const rest = common(r);
  return brandId && rest ? { brandId, ...rest } : null;
}

function dedupe(items: SavedMedicine[]): SavedMedicine[] {
  const seen = new Map<string, SavedMedicine>();
  for (const item of items) if (!seen.has(itemKey(item))) seen.set(itemKey(item), item);
  return [...seen.values()].slice(0, MAX_ITEMS);
}

/**
 * Read a stored or imported list: version 2 as it is; version 1 (or the older bare array) goes to
 * `legacy` until migrated. Invalid items are dropped; an unknown future version gives an empty list.
 */
export function parseList(raw: unknown): MyMedicinesList {
  let items: unknown[] = [];
  let version: unknown = undefined;
  if (Array.isArray(raw)) items = raw;
  else if (raw && typeof raw === "object" && Array.isArray((raw as { items?: unknown }).items)) {
    version = (raw as { version?: unknown }).version;
    items = (raw as { items: unknown[] }).items;
  }
  if (version === FORMAT_VERSION) {
    return { version: FORMAT_VERSION, items: dedupe(items.map(toSavedMedicine).filter((m) => m !== null)) };
  }
  if (version === undefined || version === 1) {
    const legacy = items.map(toLegacy).filter((m) => m !== null);
    const byId = new Map(legacy.map((m) => [m.brandId, m]));
    return { version: FORMAT_VERSION, items: [], legacy: [...byId.values()].slice(0, MAX_ITEMS) };
  }
  return EMPTY_LIST;
}

/** Parse the JSON text of a stored or imported list; anything broken gives an empty list. */
export function parseListText(raw: string | null): MyMedicinesList {
  if (!raw) return EMPTY_LIST;
  try {
    return parseList(JSON.parse(raw));
  } catch {
    return EMPTY_LIST;
  }
}

/** Version 1 items -> version 2, with the public brand index. Unmatched items are kept. */
export function migrate(list: MyMedicinesList, index: BrandIndexItem[]): MyMedicinesList {
  if (!list.legacy?.length) return list;
  const converted = list.legacy.map(({ brandId, ...rest }): SavedMedicine => ({
    ...rest,
    brandCode: findBrandCode(index, { id: brandId, ...rest }),
  }));
  return { version: FORMAT_VERSION, items: dedupe([...list.items, ...converted]) };
}

// ---------------------------------------------------------------- changes (pure)

/** Add a medicine, or update it if that brand is already saved (keeping its first-saved day). */
export function upsert(list: MyMedicinesList, item: SavedMedicine): MyMedicinesList {
  const key = itemKey(item);
  const existing = list.items.find((m) => itemKey(m) === key);
  const merged: SavedMedicine = existing
    ? {
        ...existing,
        ...item,
        addedOn: existing.addedOn,
        unitsPerDay: item.unitsPerDay ?? existing.unitsPerDay,
        reminderTimes: item.reminderTimes.length ? item.reminderTimes : existing.reminderTimes,
      }
    : item;
  const items = existing ? list.items.map((m) => (itemKey(m) === key ? merged : m)) : [...list.items, merged];
  return { version: FORMAT_VERSION, items: items.slice(0, MAX_ITEMS), legacy: list.legacy };
}

export function update(
  list: MyMedicinesList,
  key: string,
  change: Partial<Pick<SavedMedicine, "unitsPerDay" | "reminderTimes">>,
): MyMedicinesList {
  return {
    version: FORMAT_VERSION,
    legacy: list.legacy,
    items: list.items.map((m) =>
      itemKey(m) === key
        ? {
            ...m,
            ...("unitsPerDay" in change ? { unitsPerDay: units(change.unitsPerDay) } : {}),
            ...(change.reminderTimes ? { reminderTimes: cleanTimes(change.reminderTimes) } : {}),
          }
        : m,
    ),
  };
}

export function remove(list: MyMedicinesList, key: string): MyMedicinesList {
  return { version: FORMAT_VERSION, items: list.items.filter((m) => itemKey(m) !== key), legacy: list.legacy };
}

/** Merge an imported list into the current one (imported entries update matching brands). */
export function merge(current: MyMedicinesList, imported: MyMedicinesList): MyMedicinesList {
  const merged = imported.items.reduce(upsert, current);
  const legacy = [...(current.legacy ?? []), ...(imported.legacy ?? [])];
  return legacy.length ? { ...merged, legacy } : { version: FORMAT_VERSION, items: merged.items };
}

export function today(now: Date = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/** A saved medicine for one brand of a ranking page. */
export function fromRanking(
  data: Pick<AlternativesResponse, "generic" | "strength" | "dosage_form">,
  brand: Pick<RankedAlternative, "code" | "name">,
  unitsPerDay: number | null,
): SavedMedicine {
  return {
    brandCode: brand.code,
    brandName: brand.name,
    genericName: data.generic.name,
    strength: data.strength,
    dosageForm: data.dosage_form,
    unitsPerDay,
    reminderTimes: [],
    addedOn: today(),
  };
}

// ---------------------------------------------------------------- comparing with the ranking

export type Comparison = {
  rank: number;
  total: number;
  /** The top-ranked brand when it is not the saved one. */
  top: { code: string; name: string; manufacturer: string; price: number } | null;
  samePrice: boolean;
  /** Top-ranked minus saved, for 30 units (negative = the top-ranked one costs less). */
  differencePer30: number | null;
  /** Same, per month, when the user gave units per day. */
  differencePerMonth: number | null;
};

/** Where a saved medicine stands in its group today; null when the brand is no longer listed. */
export function compare(item: SavedMedicine, data: AlternativesResponse): Comparison | null {
  const mine = data.alternatives.find((a) => a.code === item.brandCode);
  if (!mine) return null;
  const best = data.alternatives[0];
  const isTop = best.code === mine.code;
  const diff = best.price_per_unit - mine.price_per_unit;
  const round = (v: number) => Math.round(v * 100) / 100;
  return {
    rank: mine.rank,
    total: data.alternatives.length,
    top: isTop ? null : { code: best.code, name: best.name, manufacturer: best.manufacturer.name, price: best.price_per_unit },
    samePrice: !isTop && Math.round(best.price_per_unit * 100) === Math.round(mine.price_per_unit * 100),
    differencePer30: isTop ? null : round(diff * 30),
    differencePerMonth: isTop || item.unitsPerDay === null ? null : round(diff * item.unitsPerDay * 30),
  };
}

// ---------------------------------------------------------------- browser storage

const CHANGED = "medwise:my-medicines";

function storage(): Storage | null {
  try {
    const s = window.localStorage;
    const probe = "__medwise_probe__";
    s.setItem(probe, "1");
    s.removeItem(probe);
    return s;
  } catch {
    return null;
  }
}

export function storageAvailable(): boolean {
  return typeof window !== "undefined" && storage() !== null;
}

export function loadList(): MyMedicinesList {
  try {
    return parseListText(storage()?.getItem(STORAGE_KEY) ?? null);
  } catch {
    return EMPTY_LIST;
  }
}

/** Save the list on this device; false when the browser does not allow it. While some version 1
 * items are not migrated yet, the stored text is left as it is (so nothing can be lost). */
export function saveList(list: MyMedicinesList): boolean {
  try {
    const s = storage();
    if (!s) return false;
    if (list.legacy?.length) return false;
    if (list.items.length === 0) s.removeItem(STORAGE_KEY);
    else s.setItem(STORAGE_KEY, JSON.stringify({ version: FORMAT_VERSION, items: list.items }));
    window.dispatchEvent(new Event(CHANGED));
    return true;
  } catch {
    return false;
  }
}

/** For useSyncExternalStore: changes in this tab and in other tabs. */
export function subscribe(onChange: () => void): () => void {
  const onStorage = (event: StorageEvent) => event.key === STORAGE_KEY && onChange();
  window.addEventListener(CHANGED, onChange);
  window.addEventListener("storage", onStorage);
  return () => {
    window.removeEventListener(CHANGED, onChange);
    window.removeEventListener("storage", onStorage);
  };
}

/** For useSyncExternalStore: the stored text (a stable value between changes). */
export function snapshot(): string {
  try {
    return storage()?.getItem(STORAGE_KEY) ?? "";
  } catch {
    return "";
  }
}
