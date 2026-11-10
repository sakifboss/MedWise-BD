import { describe, expect, it } from "vitest";

import { DICTIONARIES } from "@/i18n/dictionaries";

import {
  closestArea,
  directionsHref,
  distanceMetres,
  insideBox,
  isCityOnly,
  nearest,
  placeOf,
  roundDistance,
  telHref,
  type AreaItem,
  type Bbox,
  type PharmacyItem,
} from "./pharmacies";

const SYLHET: Bbox = [24.86, 91.82, 24.95, 91.93];
const ZINDABAZAR = { lat: 24.8967, lon: 91.871 };

function pharmacy(id: number, name: string, lat: number, lon: number): PharmacyItem {
  return { id, name, name_bn: null, lat, lon, address: null, phone: null, phone_from_osm: false, is_partner: false };
}

describe("distanceMetres", () => {
  it("is zero at the same place and about 111 m per thousandth of a degree of latitude", () => {
    expect(distanceMetres(ZINDABAZAR, ZINDABAZAR)).toBe(0);
    expect(distanceMetres({ lat: 24, lon: 91 }, { lat: 24.001, lon: 91 })).toBeCloseTo(111.2, 0);
  });

  it("matches a known city distance (Zindabazar to Ambarkhana, about 1 km)", () => {
    const d = distanceMetres(ZINDABAZAR, { lat: 24.9058, lon: 91.8708 });
    expect(d).toBeGreaterThan(900);
    expect(d).toBeLessThan(1100);
  });
});

describe("insideBox", () => {
  it("accepts Sylhet city and rejects Dhaka", () => {
    expect(insideBox(ZINDABAZAR, SYLHET)).toBe(true);
    expect(insideBox({ lat: 23.8103, lon: 90.4125 }, SYLHET)).toBe(false);
    expect(insideBox({ lat: 24.95, lon: 91.93 }, SYLHET)).toBe(true); // the edge counts
  });
});

describe("nearest", () => {
  const list = [
    pharmacy(1, "Far", 24.94, 91.92),
    pharmacy(2, "Near B", 24.897, 91.871),
    pharmacy(3, "Near A", 24.897, 91.871),
    pharmacy(4, "Middle", 24.91, 91.87),
  ];

  it("sorts closest first, breaks ties by name and adds the distance", () => {
    const result = nearest(list, ZINDABAZAR);
    expect(result.map((p) => p.name)).toEqual(["Near A", "Near B", "Middle", "Far"]);
    expect(result[0].metres).toBeCloseTo(distanceMetres(ZINDABAZAR, list[2]), 6);
  });

  it("returns at most the asked number and does not change the input", () => {
    const before = list.map((p) => p.id);
    expect(nearest(list, ZINDABAZAR, 2)).toHaveLength(2);
    expect(list.map((p) => p.id)).toEqual(before);
    const many = Array.from({ length: 25 }, (_, i) => pharmacy(i, `P${i}`, 24.9, 91.87 + i / 1000));
    expect(nearest(many, ZINDABAZAR)).toHaveLength(10);
  });
});

describe("formatting", () => {
  it("rounds distances for people", () => {
    expect(roundDistance(3)).toEqual({ value: 10, unit: "m" });
    expect(roundDistance(346)).toEqual({ value: 350, unit: "m" });
    expect(roundDistance(996)).toEqual({ value: 1, unit: "km" });
    expect(roundDistance(1260)).toEqual({ value: 1.3, unit: "km" });
  });

  it("shows distances in English and Bangla", () => {
    expect(DICTIONARIES.en.fmt.distance(346)).toBe("350 m");
    expect(DICTIONARIES.en.fmt.distance(1260)).toBe("1.3 km");
    expect(DICTIONARIES.bn.fmt.distance(346)).toBe("৩৫০ মিটার");
    expect(DICTIONARIES.bn.fmt.distance(1260)).toBe("১.৩ কিমি");
  });

  it("makes tel: links with digits only", () => {
    expect(telHref("+880 1711-000001")).toBe("tel:+8801711000001");
    expect(telHref("(0821) 71 0000")).toBe("tel:0821710000");
  });

  it("puts only the destination in the directions link", () => {
    const href = directionsHref({ lat: 24.8967, lon: 91.871 });
    expect(href).toBe("https://www.google.com/maps/dir/?api=1&destination=24.896700,91.871000");
    expect(href).not.toContain("origin");
  });
});

describe("where a pharmacy is", () => {
  const areas: AreaItem[] = [
    { id: 1, name: "Zindabazar", name_bn: "জিন্দাবাজার", lat: 24.8967, lon: 91.871 },
    { id: 2, name: "Ambarkhana", name_bn: "আম্বরখানা", lat: 24.9058, lon: 91.8708 },
  ];
  const at = (address: string | null, lat = 24.8971, lon = 91.8705) => ({ address, lat, lon });

  it("treats an empty or city-only address as no address, in any case, en or bn", () => {
    for (const a of [null, "", "  ", "Sylhet", "sylhet", "SYLHET.", " Sylhet, ", "সিলেট", "সিলেট।"]) {
      expect(isCityOnly(a), JSON.stringify(a)).toBe(true);
    }
    expect(isCityOnly("Shahjalal Uposhahar Main Road")).toBe(false);
    expect(isCityOnly("Sylhet Road, Ambarkhana")).toBe(false);
  });

  it("shows the closest area instead of a city-only or missing address", () => {
    expect(placeOf(at("Sylhet"), areas)).toEqual({ near: areas[0] });
    expect(placeOf(at(null, 24.9050, 91.8710), areas)).toEqual({ near: areas[1] });
    expect(placeOf(at("সিলেট"), areas)).toEqual({ near: areas[0] });
  });

  it("keeps a real street address as it is", () => {
    expect(placeOf(at("বন্দর বাজার সড়ক"), areas)).toEqual({ address: "বন্দর বাজার সড়ক" });
    expect(placeOf(at(" Shahjalal Uposhahar Main Road "), areas)).toEqual({ address: "Shahjalal Uposhahar Main Road" });
  });

  it("has nothing to say without areas", () => {
    expect(closestArea({ lat: 24.9, lon: 91.87 }, [])).toBeNull();
    expect(placeOf(at(null), [])).toBeNull();
  });

  it("says 'Near <area>' in English and Bangla", () => {
    expect(DICTIONARIES.en.pharmacies.near("Zindabazar")).toBe("Near Zindabazar");
    expect(DICTIONARIES.bn.pharmacies.near("জিন্দাবাজার")).toBe("জিন্দাবাজার-এর কাছে");
  });
});
