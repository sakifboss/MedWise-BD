"use client";

import { BadgeCheck, Loader2, LocateFixed, MapPin, Navigation, Phone } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useDict } from "@/i18n/client";
import { api, isRateLimited } from "@/lib/api";
import {
  NEAREST_COUNT,
  OSM_COPYRIGHT_URL,
  directionsHref,
  insideBox,
  nearest,
  telHref,
  type AreaItem,
  type Bbox,
  type PharmaciesData,
  type Point,
} from "@/lib/pharmacies";

type LocationResult = Point | "denied" | "unsupported";
type Status = "closed" | "working" | "ready" | "failed" | "limited";
type Note = "denied" | "unsupported" | "outside" | null;

/** The browser's position, asked only after the user taps the button. It stays in this tab. */
function locate(): Promise<LocationResult> {
  if (typeof navigator === "undefined" || !navigator.geolocation) return Promise.resolve("unsupported");
  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
      (error) => resolve(error.code === error.PERMISSION_DENIED ? "denied" : "unsupported"),
      { enableHighAccuracy: false, timeout: 15_000, maximumAge: 300_000 },
    );
  });
}

async function loadList(cached: PharmaciesData | null): Promise<PharmaciesData | "failed" | "limited"> {
  if (cached) return cached;
  try {
    return await api.pharmacies();
  } catch (error) {
    return isRateLimited(error) ? "limited" : "failed";
  }
}

export function OsmCredit({ before }: { before: string }) {
  return (
    <p className="text-xs text-muted-foreground" data-testid="osm-credit">
      {before}
      <a href={OSM_COPYRIGHT_URL} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2">
        © OpenStreetMap contributors
      </a>
    </p>
  );
}

/**
 * "Find pharmacies near me (Sylhet)": real places from OpenStreetMap (and later the team's
 * survey). We never claim a shop has a medicine. Distances are worked out in the browser.
 */
export function PharmacyFinder() {
  const t = useDict();
  const f = t.pharmacies;
  const [status, setStatus] = useState<Status>("closed");
  const [data, setData] = useState<PharmaciesData | null>(null);
  const [you, setYou] = useState<Point | null>(null);
  const [note, setNote] = useState<Note>(null);
  const [areaId, setAreaId] = useState<number | null>(null);

  const label = (item: { name: string; name_bn: string | null }) =>
    t.lang === "bn" && item.name_bn ? item.name_bn : item.name;

  async function start() {
    setStatus("working");
    const [loaded, position] = await Promise.all([loadList(data), locate()]);
    if (typeof loaded === "string") {
      setStatus(loaded);
      return;
    }
    setData(loaded);
    if (typeof position === "string") {
      setYou(null);
      setNote(position);
    } else if (!insideBox(position, loaded.bbox as Bbox)) {
      setYou(null);
      setNote("outside");
    } else {
      setYou(position);
      setNote(null);
      setAreaId(null);
    }
    setStatus("ready");
  }

  const area: AreaItem | undefined = data?.areas.find((a) => a.id === areaId);
  const origin: Point | null = you ?? area ?? null;
  const results = data && origin ? nearest(data.pharmacies, origin) : [];

  return (
    <Card className="print:hidden" data-testid="pharmacy-finder">
      <CardContent className="space-y-3">
        {status === "closed" || status === "working" ? (
          <Button variant="outline" onClick={start} disabled={status === "working"}>
            {status === "working" ? <Loader2 aria-hidden className="animate-spin" /> : <MapPin aria-hidden />}
            {status === "working" ? f.locating : f.find}
          </Button>
        ) : (
          <h2 className="flex items-center gap-1.5 font-medium">
            <MapPin aria-hidden className="size-4" />
            {f.find}
          </h2>
        )}

        <p className="text-sm font-medium" data-testid="no-stock-note">
          {f.noStock}
        </p>

        {(status === "failed" || status === "limited") && (
          <div className="space-y-2" role="alert">
            <p className="text-sm text-destructive">{status === "limited" ? t.tooMany : f.failed}</p>
            <Button variant="outline" size="sm" onClick={start}>
              {f.retry}
            </Button>
          </div>
        )}

        {status === "ready" && data && (
          <>
            {note && (
              <p className="text-sm" role="status" data-testid="location-note">
                {f[note]}
              </p>
            )}
            {!you && (
              <div className="flex flex-wrap items-end gap-2">
                <label className="grid gap-1 text-sm">
                  <span className="text-muted-foreground">{f.pickArea}</span>
                  <select
                    className="h-9 rounded-lg border bg-background px-2 text-sm"
                    value={areaId ?? ""}
                    onChange={(e) => setAreaId(e.target.value ? Number(e.target.value) : null)}
                    data-testid="area-picker"
                  >
                    <option value="">{f.choose}</option>
                    {[...data.areas]
                      .sort((a, b) => label(a).localeCompare(label(b), t.lang))
                      .map((a) => (
                        <option key={a.id} value={a.id}>
                          {label(a)}
                        </option>
                      ))}
                  </select>
                </label>
                {note !== "unsupported" && (
                  <Button variant="ghost" size="sm" onClick={start}>
                    <LocateFixed aria-hidden />
                    {f.useLocation}
                  </Button>
                )}
              </div>
            )}

            {origin && (
              <div className="space-y-2">
                <p className="text-sm text-muted-foreground">
                  {you
                    ? f.nearYou(t.fmt.int(Math.min(NEAREST_COUNT, results.length)))
                    : f.nearArea(t.fmt.int(Math.min(NEAREST_COUNT, results.length)), area ? label(area) : "")}
                </p>
                <ol className="divide-y rounded-lg border" data-testid="pharmacy-list">
                  {results.map((p) => (
                    <li key={p.id} className="space-y-1.5 p-3 text-sm" data-testid="pharmacy">
                      <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                        <span className="font-medium">{label(p)}</span>
                        <span className="text-muted-foreground" data-testid="distance">
                          {t.fmt.distance(p.metres)}
                        </span>
                      </div>
                      {p.address && <p className="text-muted-foreground">{p.address}</p>}
                      {p.is_partner && (
                        <Badge variant="secondary" className="gap-1">
                          <BadgeCheck aria-hidden />
                          {f.partner}
                        </Badge>
                      )}
                      <div className="flex flex-wrap items-center gap-2">
                        {p.phone ? (
                          <a href={telHref(p.phone)} className="inline-flex items-center gap-1 font-medium text-primary">
                            <Phone aria-hidden className="size-3.5" />
                            {f.call} {p.phone}
                          </a>
                        ) : (
                          <span className="text-xs text-muted-foreground">{f.noPhone}</span>
                        )}
                        <a
                          href={directionsHref(p)}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 font-medium text-primary"
                        >
                          <Navigation aria-hidden className="size-3.5" />
                          {f.directions}
                        </a>
                      </div>
                      {p.phone && p.phone_from_osm && <p className="text-xs text-muted-foreground">{f.osmPhone}</p>}
                    </li>
                  ))}
                </ol>
                <p className="text-xs text-muted-foreground">{f.straightLine}</p>
              </div>
            )}
          </>
        )}

        <p className="text-xs text-muted-foreground">{f.privacy}</p>
        {status === "ready" && <OsmCredit before={f.creditBefore} />}
      </CardContent>
    </Card>
  );
}
