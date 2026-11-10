/**
 * Offline copies of pages, kept by the service worker (public/sw.js).
 * Pure helpers first (unit-tested), then the browser-only parts.
 */
import { rankingHref } from "@/lib/format";

/** Must match PAGES in public/sw.js (a unit test checks). */
export const PAGES_CACHE = "medwise-pages-v2";
const SAVED_AT_META = 'meta[name="medwise-saved-at"]';
const GENERIC_PAGE = /^\/generics\/(\d+)$/;

export type GenericForOffline = {
  id: number;
  presentations: { strength: string; dosage_form: string }[];
};

/** Every generic page and every ranking page: what "Save all medicines" saves. */
export function offlineUrls(generics: GenericForOffline[]): string[] {
  const urls: string[] = [];
  for (const g of generics) {
    urls.push(`/generics/${g.id}`);
    for (const p of g.presentations) urls.push(rankingHref(g.id, p.strength, p.dosage_form));
  }
  return [...new Set(urls)];
}

/** The page title without the site name ("Paracetamol · MedWise BD" -> "Paracetamol"). */
export function titleFromHtml(html: string): string | null {
  const match = /<title[^>]*>([^<]*)<\/title>/i.exec(html);
  if (!match) return null;
  const title = match[1]
    .replace(/&amp;/g, "&")
    .replace(/&#x27;|&#39;/g, "'")
    .replace(/&quot;/g, '"')
    .split(" · ")[0]
    .trim();
  return title || null;
}

/** Generic id from a saved page URL, or null for other pages. */
export function genericIdFromUrl(url: string): number | null {
  const match = GENERIC_PAGE.exec(new URL(url, "https://x.invalid").pathname);
  return match ? Number(match[1]) : null;
}

// ---------------------------------------------------------------- browser only

/** When this page was served from the offline copy: when it was saved (ISO text), else null. */
export function savedAtOfThisPage(): string | null {
  return document.querySelector(SAVED_AT_META)?.getAttribute("content") || null;
}

/** A valid date from the saved-at text, or null. */
export function parseSavedAt(value: string | null): Date | null {
  const date = value ? new Date(value) : null;
  return date && !Number.isNaN(date.getTime()) ? date : null;
}

export type SavedMedicine = { id: number; name: string; href: string };

/** Generic pages saved on this device, by name. */
export async function savedMedicines(): Promise<SavedMedicine[]> {
  try {
    if (!("caches" in window)) return [];
    const cache = await caches.open(PAGES_CACHE);
    const found: SavedMedicine[] = [];
    for (const request of await cache.keys()) {
      const id = genericIdFromUrl(request.url);
      if (id === null) continue;
      const response = await cache.match(request);
      const name = response ? titleFromHtml(await response.text()) : null;
      if (name) found.push({ id, name, href: `/generics/${id}` });
    }
    return found.sort((a, b) => a.name.localeCompare(b.name));
  } catch {
    return [];
  }
}

export type SaveProgress = { done: number; total: number };
export type SaveResult = { saved: number; failed: number; total: number };

/** Ask the service worker to save these pages; resolves when it has finished. */
export async function saveForOffline(
  urls: string[],
  onProgress: (progress: SaveProgress) => void,
): Promise<SaveResult> {
  const registration = await navigator.serviceWorker.ready;
  const worker = registration.active;
  if (!worker) throw new Error("no active service worker");
  return new Promise((resolve) => {
    const channel = new MessageChannel();
    channel.port1.onmessage = (event: MessageEvent) => {
      const data = event.data as { type: string } & SaveProgress & SaveResult;
      if (data.type === "progress") onProgress({ done: data.done, total: data.total });
      if (data.type === "done") {
        channel.port1.close();
        resolve({ saved: data.saved, failed: data.failed, total: data.total });
      }
    };
    worker.postMessage({ type: "save-all", urls }, [channel.port2]);
  });
}

export function canSaveForOffline(): boolean {
  return typeof navigator !== "undefined" && "serviceWorker" in navigator && "caches" in window;
}
