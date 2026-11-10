/**
 * "My Medicines": a list kept only on this device (localStorage). Nothing about it is sent to
 * the MedWise BD backend; pages only call the public ranking and interaction APIs by brand id.
 *
 * Pure helpers first (unit-tested), then the browser-only storage parts.
 */
import type { AlternativesResponse, RankedAlternative } from "@/lib/api";

export const STORAGE_KEY = "medwise.myMedicines";
export const FORMAT_VERSION = 1;
const MAX_ITEMS = 50;
const MAX_TIMES = 6;
const TIME = /^([01]\d|2[0-3]):[0-5]\d$/;
const DATE = /^\d{4}-\d{2}-\d{2}$/;

/** One saved medicine: what the brand is, and only what the user typed (never a suggestion). */
export type SavedMedicine = {
  brandId: number;
  brandName: string;
  genericId: number;
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

export type MyMedicinesList = { version: typeof FORMAT_VERSION; items: SavedMedicine[] };

export const EMPTY_LIST: MyMedicinesList = { version: FORMAT_VERSION, items: [] };

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

/** A valid saved medicine from unknown data, or null. Unknown fields are dropped. */
export function toSavedMedicine(raw: unknown): SavedMedicine | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  const brandId = positiveInt(r.brandId);
  const genericId = positiveInt(r.genericId);
  const brandName = text(r.brandName);
  const genericName = text(r.genericName);
  const strength = text(r.strength, 50);
  const dosageForm = text(r.dosageForm, 50);
  if (!brandId || !genericId || !brandName || !genericName || !strength || !dosageForm) return null;
  const addedOn = typeof r.addedOn === "string" && DATE.test(r.addedOn) ? r.addedOn : today();
  return {
    brandId,
    brandName,
    genericId,
    genericName,
    strength,
    dosageForm,
    unitsPerDay: units(r.unitsPerDay),
    reminderTimes: cleanTimes(r.reminderTimes),
    addedOn,
  };
}

/**
 * Read a stored or imported list. Accepts the current format and older shapes (a bare array of
 * items, saved before the format had a version), drops invalid items and keeps one per brand.
 */
export function parseList(raw: unknown): MyMedicinesList {
  let items: unknown[] = [];
  if (Array.isArray(raw)) items = raw; // unversioned
  else if (raw && typeof raw === "object" && Array.isArray((raw as { items?: unknown }).items)) {
    const version = (raw as { version?: unknown }).version;
    if (version === undefined || version === FORMAT_VERSION) items = (raw as { items: unknown[] }).items;
  }
  const byBrand = new Map<number, SavedMedicine>();
  for (const item of items) {
    const saved = toSavedMedicine(item);
    if (saved && !byBrand.has(saved.brandId)) byBrand.set(saved.brandId, saved);
  }
  return { version: FORMAT_VERSION, items: [...byBrand.values()].slice(0, MAX_ITEMS) };
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

// ---------------------------------------------------------------- changes (pure)

/** Add a medicine, or update it if that brand is already saved (keeping its first-saved day). */
export function upsert(list: MyMedicinesList, item: SavedMedicine): MyMedicinesList {
  const existing = list.items.find((m) => m.brandId === item.brandId);
  const merged: SavedMedicine = existing
    ? {
        ...existing,
        ...item,
        addedOn: existing.addedOn,
        unitsPerDay: item.unitsPerDay ?? existing.unitsPerDay,
        reminderTimes: item.reminderTimes.length ? item.reminderTimes : existing.reminderTimes,
      }
    : item;
  const others = list.items.filter((m) => m.brandId !== item.brandId);
  const items = existing
    ? list.items.map((m) => (m.brandId === item.brandId ? merged : m))
    : [...others, merged];
  return { version: FORMAT_VERSION, items: items.slice(0, MAX_ITEMS) };
}

export function update(
  list: MyMedicinesList,
  brandId: number,
  change: Partial<Pick<SavedMedicine, "unitsPerDay" | "reminderTimes">>,
): MyMedicinesList {
  return {
    version: FORMAT_VERSION,
    items: list.items.map((m) =>
      m.brandId === brandId
        ? {
            ...m,
            ...("unitsPerDay" in change ? { unitsPerDay: units(change.unitsPerDay) } : {}),
            ...(change.reminderTimes ? { reminderTimes: cleanTimes(change.reminderTimes) } : {}),
          }
        : m,
    ),
  };
}

export function remove(list: MyMedicinesList, brandId: number): MyMedicinesList {
  return { version: FORMAT_VERSION, items: list.items.filter((m) => m.brandId !== brandId) };
}

/** Merge an imported list into the current one (imported entries update matching brands). */
export function merge(current: MyMedicinesList, imported: MyMedicinesList): MyMedicinesList {
  return imported.items.reduce(upsert, current);
}

export function today(now: Date = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/** A saved medicine for one brand of a ranking page. */
export function fromRanking(
  data: Pick<AlternativesResponse, "generic" | "strength" | "dosage_form">,
  brand: Pick<RankedAlternative, "brand_id" | "name">,
  unitsPerDay: number | null,
): SavedMedicine {
  return {
    brandId: brand.brand_id,
    brandName: brand.name,
    genericId: data.generic.id,
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
  top: { brandId: number; name: string; manufacturer: string; price: number } | null;
  samePrice: boolean;
  /** Top-ranked minus saved, for 30 units (negative = the top-ranked one costs less). */
  differencePer30: number | null;
  /** Same, per month, when the user gave units per day. */
  differencePerMonth: number | null;
};

/** Where a saved medicine stands in its group today; null when the brand is no longer listed. */
export function compare(item: SavedMedicine, data: AlternativesResponse): Comparison | null {
  const mine = data.alternatives.find((a) => a.brand_id === item.brandId);
  if (!mine) return null;
  const best = data.alternatives[0];
  const isTop = best.brand_id === mine.brand_id;
  const diff = best.price_per_unit - mine.price_per_unit;
  const round = (v: number) => Math.round(v * 100) / 100;
  return {
    rank: mine.rank,
    total: data.alternatives.length,
    top: isTop
      ? null
      : { brandId: best.brand_id, name: best.name, manufacturer: best.manufacturer.name, price: best.price_per_unit },
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

/** Save the list on this device; false when the browser does not allow it. */
export function saveList(list: MyMedicinesList): boolean {
  try {
    const s = storage();
    if (!s) return false;
    if (list.items.length === 0) s.removeItem(STORAGE_KEY);
    else s.setItem(STORAGE_KEY, JSON.stringify(list));
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
