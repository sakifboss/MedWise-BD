"use client";

import { ExternalLink, Loader2, Plus, Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { VoiceSearchButton } from "@/components/voice-search-button";
import { useDict } from "@/i18n/client";
import { api, isRateLimited, type BrandIndex, type GenericListItem, type SearchResult } from "@/lib/api";
import { MAX_FREE_NAME, type RxSource } from "@/lib/rx";
import {
  RETRY_AFTER_429_MS,
  SEARCH_DEBOUNCE_MS,
  SearchCache,
  SearchPacer,
  searchKey,
} from "@/lib/rx-search";

type Status = "idle" | "short" | "loading" | "busy" | "done" | "error";
type BrandInfo = BrandIndex["brands"][number];

/**
 * Medicine search for the Rx Pad. Search requests carry only the typed text; rank, price and
 * approvals come from the brand index (fetched once, looked up on the device).
 */
export function MedicinePicker({
  disabled,
  onPick,
}: {
  disabled: boolean;
  onPick: (source: RxSource) => void;
}) {
  const t = useDict();
  const s = t.rx.search;
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [openGeneric, setOpenGeneric] = useState<number | null>(null);
  const [brands, setBrands] = useState<Map<string, BrandInfo>>(new Map());
  const [generics, setGenerics] = useState<Map<number, GenericListItem>>(new Map());
  const [voiceMessage, setVoiceMessage] = useState<string | null>(null);
  const pacer = useRef(new SearchPacer());
  const cache = useRef(new SearchCache<SearchResult[]>());
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const inflight = useRef<AbortController | undefined>(undefined);
  const current = useRef<string | null>(null);

  useEffect(() => {
    // Public catalog data, the same for everyone: fetched once for the whole session.
    api.brandIndex().then((index) => setBrands(new Map(index.brands.map((b) => [b.code, b])))).catch(() => {});
    api.generics().then((list) => setGenerics(new Map(list.map((g) => [g.id, g])))).catch(() => {});
    return () => {
      clearTimeout(timer.current);
      inflight.current?.abort();
    };
  }, []);

  async function run(key: string, text: string) {
    if (current.current !== key) return;
    const wait = pacer.current.delay();
    if (wait > 0) {
      setStatus("busy");
      timer.current = setTimeout(() => void run(key, text), wait);
      return;
    }
    pacer.current.record();
    inflight.current?.abort();
    const controller = new AbortController();
    inflight.current = controller;
    try {
      const response = await api.search(text, { limit: 8, signal: controller.signal });
      cache.current.set(key, response.results);
      if (current.current === key) {
        setResults(response.results);
        setStatus("done");
      }
    } catch (error) {
      if (controller.signal.aborted || current.current !== key) return;
      if (isRateLimited(error)) {
        setStatus("busy");
        timer.current = setTimeout(() => void run(key, text), RETRY_AFTER_429_MS);
      } else {
        setStatus("error");
      }
    }
  }

  function onChange(value: string) {
    setQuery(value);
    setOpenGeneric(null);
    clearTimeout(timer.current);
    const key = searchKey(value);
    current.current = key;
    if (!key) {
      inflight.current?.abort();
      setResults([]);
      setStatus(value.trim() ? "short" : "idle");
      return;
    }
    const cached = cache.current.get(key);
    if (cached) {
      setResults(cached);
      setStatus("done");
      return;
    }
    setStatus("loading");
    timer.current = setTimeout(() => void run(key, value.trim()), SEARCH_DEBOUNCE_MS);
  }

  function pick(source: RxSource) {
    onPick(source);
    onChange("");
  }

  function pickBrand(result: SearchResult) {
    const info = result.code ? brands.get(result.code) : undefined;
    if (!info) return;
    pick({
      kind: "brand",
      code: info.code,
      name: info.name,
      genericId: info.generic_id,
      generic: info.generic,
      strength: info.strength,
      dosageForm: info.dosage_form,
      manufacturer: info.manufacturer,
      pricePerUnit: info.price_per_unit,
      priceCheckedOn: info.price_checked_on ?? null,
      rank: info.rank,
      groupSize: info.group_size,
      approvals: info.approvals,
    });
  }

  const freeName = query.trim().slice(0, MAX_FREE_NAME);

  return (
    <div className="space-y-2" data-testid="medicine-picker">
      <label htmlFor="rx-medicine-search" className="text-sm font-medium">
        {s.label}
      </label>
      <div className="relative flex items-center gap-2">
        <Search aria-hidden className="pointer-events-none absolute left-2.5 size-4 text-muted-foreground" />
        <Input
          id="rx-medicine-search"
          type="search"
          value={query}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
          placeholder={s.placeholder}
          autoComplete="off"
          spellCheck={false}
          className="pl-8"
          maxLength={60}
        />
        <VoiceSearchButton
          onTranscript={(text, final) => (final ? onChange(text) : setQuery(text))}
          onMessage={setVoiceMessage}
        />
      </div>
      <p className="text-xs text-muted-foreground">{disabled ? s.maxLines(t.fmt.int(12)) : s.onlySearchSent}</p>
      {voiceMessage && <p className="text-xs text-muted-foreground">{voiceMessage}</p>}
      {status === "short" && <p className="text-xs text-muted-foreground">{s.minChars}</p>}
      {(status === "loading" || status === "busy") && (
        <p className="flex items-center gap-1 text-xs text-muted-foreground" role="status">
          <Loader2 aria-hidden className="size-3 animate-spin" />
          {status === "busy" ? s.busy : s.searching}
        </p>
      )}
      {status === "error" && <p className="text-xs text-destructive">{s.error}</p>}

      {(status === "done" || status === "busy") && (
        <ul className="divide-y rounded-lg border" data-testid="medicine-results">
          {results.length === 0 && <li className="p-2 text-sm text-muted-foreground">{s.none}</li>}
          {results.map((r) => {
            if (r.type === "brand") {
              const info = r.code ? brands.get(r.code) : undefined;
              return (
                <li key={`b${r.id}`} className="flex items-start justify-between gap-2 p-2 text-sm">
                  <div className="min-w-0">
                    <p className="font-medium">
                      {r.name} <span className="font-normal">{r.strength}</span>{" "}
                      <span className="text-muted-foreground">{r.dosage_form && t.fmt.form(r.dosage_form)}</span>
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {r.generic_name} · {r.manufacturer}
                    </p>
                    {info && (
                      <p className="text-xs text-muted-foreground">
                        {t.fmt.price(info.price_per_unit)} ·{" "}
                        {s.rankLine(t.fmt.int(info.rank), t.fmt.int(info.group_size), t.fmt.int(info.approvals))} ·{" "}
                        <a
                          href={`/alternatives/${info.code}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-0.5 underline underline-offset-2"
                        >
                          {s.ranking}
                          <ExternalLink aria-hidden className="size-3" />
                        </a>
                      </p>
                    )}
                  </div>
                  <Button size="sm" variant="outline" disabled={!info} onClick={() => pickBrand(r)}>
                    <Plus aria-hidden />
                  </Button>
                </li>
              );
            }
            const generic = generics.get(r.id);
            return (
              <li key={`g${r.id}`} className="space-y-1 p-2 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <p>
                    <span className="font-medium">{r.name}</span>{" "}
                    <span className="text-xs text-muted-foreground">{s.genericOnly}</span>
                  </p>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={!generic}
                    onClick={() => setOpenGeneric(openGeneric === r.id ? null : r.id)}
                  >
                    <Plus aria-hidden />
                  </Button>
                </div>
                {openGeneric === r.id && generic && (
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">{s.choosePresentation}</p>
                    <div className="flex flex-wrap gap-1">
                      {generic.presentations.map((p) => (
                        <Button
                          key={`${p.strength}-${p.dosage_form}`}
                          size="sm"
                          variant="secondary"
                          onClick={() =>
                            pick({
                              kind: "generic",
                              genericId: generic.id,
                              generic: generic.name,
                              strength: p.strength,
                              dosageForm: p.dosage_form,
                            })
                          }
                        >
                          {p.strength} {t.fmt.form(p.dosage_form)}
                        </Button>
                      ))}
                    </div>
                  </div>
                )}
              </li>
            );
          })}
          {freeName && (
            <li className="flex items-center justify-between gap-2 p-2 text-sm">
              <div>
                <p>{s.addFree(freeName)}</p>
                <p className="text-xs text-muted-foreground">{t.rx.line.notInCatalog}</p>
              </div>
              <Button size="sm" variant="outline" onClick={() => pick({ kind: "free", name: freeName })}>
                <Plus aria-hidden />
              </Button>
            </li>
          )}
        </ul>
      )}
    </div>
  );
}
