"use client";

import { Search, X } from "lucide-react";
import { useRef, useState } from "react";

import { InteractionPanel } from "@/components/interactions/interaction-panel";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { api, type SearchResult } from "@/lib/api";

export type PickedMedicine = { kind: "brand" | "generic"; id: number; label: string; detail: string };

const DEBOUNCE_MS = 200;
const MAX_MEDICINES = 20;

function toPicked(result: SearchResult): PickedMedicine {
  return result.type === "generic"
    ? { kind: "generic", id: result.id, label: result.name, detail: "Generic" }
    : {
        kind: "brand",
        id: result.id,
        label: `${result.name} ${result.strength ?? ""}`.trim(),
        detail: result.generic_name,
      };
}

function pickedKey(m: PickedMedicine): string {
  return `${m.kind}-${m.id}`;
}

export function InteractionChecker({ initial }: { initial: PickedMedicine[] }) {
  const [picked, setPicked] = useState<PickedMedicine[]>(initial);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<PickedMedicine[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  function onChange(value: string) {
    setQuery(value);
    clearTimeout(timer.current);
    const q = value.trim();
    if (!q) {
      setResults([]);
      setMessage(null);
      return;
    }
    timer.current = setTimeout(async () => {
      try {
        const response = await api.search(q, { limit: 8 });
        setResults(response.results.map(toPicked));
        setMessage(response.results.length ? null : "No medicines found. Try another spelling.");
      } catch {
        setMessage("Search is unavailable right now.");
      }
    }, DEBOUNCE_MS);
  }

  function add(medicine: PickedMedicine) {
    if (!picked.some((m) => pickedKey(m) === pickedKey(medicine))) {
      setPicked([...picked, medicine]);
    }
    setQuery("");
    setResults([]);
  }

  const full = picked.length >= MAX_MEDICINES;
  const brandIds = picked.filter((m) => m.kind === "brand").map((m) => m.id);
  const genericIds = picked.filter((m) => m.kind === "generic").map((m) => m.id);

  return (
    <div className="space-y-6">
      <section className="space-y-3">
        <div className="relative">
          <Search
            aria-hidden
            className="pointer-events-none absolute top-1/2 left-3.5 size-5 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            type="search"
            aria-label="Add a medicine"
            placeholder={full ? `Up to ${MAX_MEDICINES} medicines` : "Brand or generic name"}
            disabled={full}
            autoComplete="off"
            value={query}
            onChange={(event) => onChange(event.target.value)}
            className="h-12 rounded-xl pl-11 text-base"
          />
        </div>
        {message && <p className="text-sm text-muted-foreground">{message}</p>}
        {results.length > 0 && (
          <ul className="divide-y overflow-hidden rounded-xl border bg-card shadow-sm">
            {results.map((r) => (
              <li key={pickedKey(r)}>
                <button
                  type="button"
                  onClick={() => add(r)}
                  className="flex w-full items-center gap-2 px-4 py-3 text-left hover:bg-muted/60 focus-visible:bg-muted/60 focus-visible:outline-none"
                >
                  <span className="font-medium">{r.label}</span>
                  <span className="text-sm text-muted-foreground">{r.detail}</span>
                </button>
              </li>
            ))}
          </ul>
        )}

        {picked.length > 0 && (
          <ul aria-label="Medicines to check" className="flex flex-wrap gap-2">
            {picked.map((m) => (
              <li key={pickedKey(m)}>
                <Badge variant="secondary" className="h-8 gap-1.5 pr-1 pl-3 text-sm">
                  {m.label}
                  <button
                    type="button"
                    onClick={() => setPicked(picked.filter((p) => pickedKey(p) !== pickedKey(m)))}
                    aria-label={`Remove ${m.label}`}
                    className="rounded-full p-1 hover:bg-foreground/10"
                  >
                    <X aria-hidden className="size-3.5" />
                  </button>
                </Badge>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-live="polite" className="space-y-2">
        <h2 className="text-lg font-semibold">Results</h2>
        {picked.length === 0 ? (
          <p className="text-sm text-muted-foreground">Add two or more medicines to check them together.</p>
        ) : (
          <InteractionPanel brandIds={brandIds} genericIds={genericIds} />
        )}
      </section>
    </div>
  );
}
