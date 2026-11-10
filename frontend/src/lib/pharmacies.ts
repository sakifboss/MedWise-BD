/**
 * Pharmacy finder helpers. Distances are worked out here, in the browser: the user's location is
 * never sent to the MedWise BD backend (the pharmacy list is fetched whole, without a position).
 */
import type { components } from "./api-schema";

export type PharmacyItem = components["schemas"]["PharmacyOut"];
export type AreaItem = components["schemas"]["AreaOut"];
export type PharmaciesData = components["schemas"]["PharmaciesResponse"];

export type Point = { lat: number; lon: number };
/** south, west, north, east */
export type Bbox = readonly [number, number, number, number];
export type NearbyPharmacy = PharmacyItem & { metres: number };

export const NEAREST_COUNT = 10;

/** Great-circle (straight-line) distance in metres. */
export function distanceMetres(a: Point, b: Point): number {
  const r = 6_371_000;
  const rad = Math.PI / 180;
  const dLat = (b.lat - a.lat) * rad;
  const dLon = (b.lon - a.lon) * rad;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLon / 2) ** 2;
  return 2 * r * Math.asin(Math.min(1, Math.sqrt(h)));
}

export function insideBox(point: Point, [south, west, north, east]: Bbox): boolean {
  return point.lat >= south && point.lat <= north && point.lon >= west && point.lon <= east;
}

/** The nearest pharmacies to a point, closest first (ties by name, so the order is stable). */
export function nearest(pharmacies: PharmacyItem[], from: Point, count = NEAREST_COUNT): NearbyPharmacy[] {
  return pharmacies
    .map((p) => ({ ...p, metres: distanceMetres(from, p) }))
    .sort((a, b) => a.metres - b.metres || a.name.localeCompare(b.name))
    .slice(0, count);
}

// An address that is only the city name tells nobody where the shop is.
const CITY_ONLY = /^(sylhet|সিলেট)$/i;

/** True when an address is empty or only says "Sylhet" / "সিলেট" (any case, trailing punctuation incl. "।"). */
export function isCityOnly(address: string | null | undefined): boolean {
  const cleaned = (address ?? "").trim().replace(/[\s.,;।]+$/u, "");
  return cleaned === "" || CITY_ONLY.test(cleaned);
}

/** The area (from sylhet_areas.json) closest to a point; null when there are no areas. */
export function closestArea(point: Point, areas: AreaItem[]): AreaItem | null {
  let best: AreaItem | null = null;
  let bestMetres = Infinity;
  for (const area of areas) {
    const m = distanceMetres(point, area);
    if (m < bestMetres) [best, bestMetres] = [area, m];
  }
  return best;
}

/**
 * Where a pharmacy is, in words: its street address when it has a real one, otherwise the
 * closest named area, worked out from its coordinates.
 */
export function placeOf(
  pharmacy: Pick<PharmacyItem, "address" | "lat" | "lon">,
  areas: AreaItem[],
): { address: string } | { near: AreaItem } | null {
  if (!isCityOnly(pharmacy.address)) return { address: pharmacy.address!.trim() };
  const area = closestArea(pharmacy, areas);
  return area ? { near: area } : null;
}

/** A distance rounded for people: whole tens of metres below 1 km, else km with one decimal. */
export function roundDistance(metres: number): { value: number; unit: "m" | "km" } {
  const tens = Math.max(10, Math.round(metres / 10) * 10);
  if (tens < 1000) return { value: tens, unit: "m" };
  return { value: Math.round(metres / 100) / 10, unit: "km" };
}

/** A tel: link with only digits and a leading +. */
export function telHref(phone: string): string {
  const plus = phone.trim().startsWith("+") ? "+" : "";
  return `tel:${plus}${phone.replace(/\D/g, "")}`;
}

/**
 * Directions in Google Maps to the pharmacy. Only the destination is in the link: the user's
 * position is not added by us (the maps app finds it itself, if the user allows).
 */
export function directionsHref(p: Point): string {
  return `https://www.google.com/maps/dir/?api=1&destination=${p.lat.toFixed(6)},${p.lon.toFixed(6)}`;
}

export const OSM_COPYRIGHT_URL = "https://www.openstreetmap.org/copyright";
