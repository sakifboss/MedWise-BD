/**
 * "Recently viewed": the last ranking and alternatives pages opened, kept only on this device
 * (localStorage). Nothing about it is sent to the MedWise BD backend. No prices are kept, so a
 * stored item never shows an old price.
 *
 * Version 2 links brand pages by their stable code (/alternatives/BR00042). A version 1 list
 * linked them by database id, which changes on re-import: those items are matched to codes with
 * the public brand index (by brand, strength and form) the first time the list is shown.
 *
 * Pure helpers first (unit-tested), then the browser-only storage parts.
 */
import { findBrandCode, type BrandIndexItem } from "@/lib/brand-index";
import { rankingHref } from "@/lib/format";

export const RECENT_KEY = "medwise.recent";
export const RECENT_VERSION = 2;
export const MAX_RECENT = 8;
const DATE = /^\d{4}-\d{2}-\d{2}$/;
// Only our own two kinds of page: a stored link can never point anywhere else.
const HREF = /^\/(alternatives\/BR\d{5}|generics\/\d+\/ranking\?strength=[^&#]+&form=[^&#]+)$/;
// Version 1 brand links, by database id: only read, to migrate them.
const LEGACY_HREF = /^\/alternatives\/(\d+)$/;

export type RecentItem = {
  kind: "alternatives" | "ranking";
  /** Brand name for an alternatives page, generic name for a ranking page. */
  name: string;
  genericName: string;
  strength: string;
  dosageForm: string;
  href: string;
  /** Day it was last opened, "YYYY-MM-DD". */
  viewedOn: string;
};

export type RecentList = {
  version: typeof RECENT_VERSION;
  items: RecentItem[];
  /** Version 1 brand items not matched to a code yet (the brand index was not available). */
  legacy?: RecentItem[];
};

export const EMPTY_RECENT: RecentList = { version: RECENT_VERSION, items: [] };

function text(value: unknown, max = 120): string | null {
  return typeof value === "string" && value.trim() && value.length <= max ? value.trim() : null;
}

export function today(now: Date = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/** A valid item from unknown data, or null. Unknown fields are dropped. */
export function toRecentItem(raw: unknown, pattern: RegExp = HREF): RecentItem | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  const kind = r.kind === "alternatives" || r.kind === "ranking" ? r.kind : null;
  const name = text(r.name);
  const genericName = text(r.genericName);
  const strength = text(r.strength, 50);
  const dosageForm = text(r.dosageForm, 50);
  const href = typeof r.href === "string" && pattern.test(r.href) ? r.href : null;
  if (!kind || !name || !genericName || !strength || !dosageForm || !href) return null;
  const viewedOn = typeof r.viewedOn === "string" && DATE.test(r.viewedOn) ? r.viewedOn : today();
  return { kind, name, genericName, strength, dosageForm, href, viewedOn };
}

/** Read a stored list; anything broken or of an unknown version gives an empty list. */
export function parseRecent(raw: string | null): RecentList {
  if (!raw) return EMPTY_RECENT;
  try {
    const data = JSON.parse(raw) as { version?: unknown; items?: unknown };
    if (!Array.isArray(data?.items)) return EMPTY_RECENT;
    if (data.version === 1) {
      // Ranking links stay valid; brand links by id wait for the brand index.
      const items = data.items.map((r) => toRecentItem(r)).filter((i) => i !== null);
      const legacy = data.items.map((r) => toRecentItem(r, LEGACY_HREF)).filter((i) => i !== null);
      return { version: RECENT_VERSION, items: unique(items), legacy: unique(legacy) };
    }
    if (data.version !== RECENT_VERSION) return EMPTY_RECENT;
    const items = unique(data.items.map((r) => toRecentItem(r)).filter((i) => i !== null));
    const pending = (data as { legacy?: unknown }).legacy;
    const legacy = Array.isArray(pending)
      ? unique(pending.map((r) => toRecentItem(r, LEGACY_HREF)).filter((i) => i !== null))
      : [];
    return legacy.length ? { version: RECENT_VERSION, items, legacy } : { version: RECENT_VERSION, items };
  } catch {
    return EMPTY_RECENT;
  }
}

function unique(items: RecentItem[]): RecentItem[] {
  const seen = new Set<string>();
  return items.filter((i) => !seen.has(i.href) && seen.add(i.href)).slice(0, MAX_RECENT);
}

/** Version 1 brand items -> code links, with the public brand index; unmatched ones are dropped
 * (it is only a list of recently opened pages). Order: most recent first, as before. */
export function migrateRecent(list: RecentList, index: BrandIndexItem[]): RecentList {
  if (!list.legacy?.length) return list;
  const converted = list.legacy.flatMap((item) => {
    const id = Number(LEGACY_HREF.exec(item.href)?.[1]);
    const code = findBrandCode(index, { id, brandName: item.name, strength: item.strength, dosageForm: item.dosageForm, genericName: item.genericName });
    return code ? [{ ...item, href: `/alternatives/${code}` }] : [];
  });
  const merged = [...list.items, ...converted].sort((a, b) => b.viewedOn.localeCompare(a.viewedOn));
  return { version: RECENT_VERSION, items: unique(merged) };
}

/** Put a page first (opening it again moves it to the top), keeping at most MAX_RECENT. */
export function addRecent(list: RecentList, item: RecentItem): RecentList {
  const others = list.items.filter((i) => i.href !== item.href);
  return { version: RECENT_VERSION, items: [item, ...others].slice(0, MAX_RECENT), legacy: list.legacy };
}

/** The item for an alternatives page (a brand) or a ranking page (a generic). */
export function recentFor(
  page:
    | { kind: "alternatives"; brandCode: string; brandName: string }
    | { kind: "ranking"; genericId: number },
  medicine: { genericName: string; strength: string; dosageForm: string },
  now: Date = new Date(),
): RecentItem {
  return {
    kind: page.kind,
    name: page.kind === "alternatives" ? page.brandName : medicine.genericName,
    ...medicine,
    href:
      page.kind === "alternatives"
        ? `/alternatives/${page.brandCode}`
        : rankingHref(page.genericId, medicine.strength, medicine.dosageForm),
    viewedOn: today(now),
  };
}

// ---------------------------------------------------------------- browser storage

const CHANGED = "medwise:recent";

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

/** Remember that this page was opened (silently does nothing when storage is unavailable). */
export function rememberPage(page: Omit<RecentItem, "viewedOn">): void {
  try {
    const s = storage();
    if (!s) return;
    const item: RecentItem = { ...page, viewedOn: today() };
    writeRecent(s, addRecent(parseRecent(s.getItem(RECENT_KEY)), item));
  } catch {
    // Full or blocked storage: the list is a convenience, never an error.
  }
}

function writeRecent(s: Storage, list: RecentList): void {
  s.setItem(RECENT_KEY, JSON.stringify(list.legacy?.length ? list : { version: list.version, items: list.items }));
  window.dispatchEvent(new Event(CHANGED));
}

/** Match version 1 brand items to codes, once the brand index is loaded. */
export function saveMigratedRecent(index: BrandIndexItem[]): void {
  try {
    const s = storage();
    if (s) writeRecent(s, migrateRecent(parseRecent(s.getItem(RECENT_KEY)), index));
  } catch {
    // ignore: tried again next time
  }
}

export function clearRecent(): void {
  try {
    storage()?.removeItem(RECENT_KEY);
    window.dispatchEvent(new Event(CHANGED));
  } catch {
    // ignore
  }
}

/** For useSyncExternalStore: changes in this tab and in other tabs. */
export function subscribeRecent(onChange: () => void): () => void {
  const onStorage = (event: StorageEvent) => event.key === RECENT_KEY && onChange();
  window.addEventListener(CHANGED, onChange);
  window.addEventListener("storage", onStorage);
  return () => {
    window.removeEventListener(CHANGED, onChange);
    window.removeEventListener("storage", onStorage);
  };
}

/** For useSyncExternalStore: the stored text (a stable value between changes). */
export function recentSnapshot(): string {
  try {
    return storage()?.getItem(RECENT_KEY) ?? "";
  } catch {
    return "";
  }
}
