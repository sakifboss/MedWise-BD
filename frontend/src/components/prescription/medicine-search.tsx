"use client";

import { Search } from "lucide-react";
import { useRef, useState } from "react";

import { Input } from "@/components/ui/input";
import { api, type MatchOption, type SearchResult } from "@/lib/api";

const DEBOUNCE_MS = 250;

function toOption(result: SearchResult): MatchOption | null {
  if (result.type !== "brand" || !result.strength || !result.dosage_form) return null;
  return {
    kind: "brand",
    brand_id: result.id,
    generic_id: result.generic_id,
    generic_name: result.generic_name,
    name: result.name,
    strength: result.strength,
    dosage_form: result.dosage_form,
    manufacturer: result.manufacturer ?? null,
    score: result.score,
    strength_matches: false,
  };
}

/** Small brand search used to correct or add a prescription medicine by hand. */
export function MedicineSearch({
  label,
  onPick,
}: {
  label: string;
  onPick: (option: MatchOption) => void;
}) {
  const [query, setQuery] = useState("");
  const [options, setOptions] = useState<MatchOption[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  function onChange(value: string) {
    setQuery(value);
    clearTimeout(timer.current);
    const q = value.trim();
    if (!q) {
      setOptions([]);
      setMessage(null);
      return;
    }
    timer.current = setTimeout(async () => {
      try {
        const response = await api.search(q, { limit: 8 });
        const found = response.results.map(toOption).filter((o): o is MatchOption => o !== null);
        setOptions(found);
        setMessage(found.length ? null : "No brands found. Try another spelling.");
      } catch {
        setMessage("Search is unavailable right now.");
      }
    }, DEBOUNCE_MS);
  }

  return (
    <div className="space-y-2">
      <div className="relative">
        <Search
          aria-hidden
          className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
        />
        <Input
          type="search"
          aria-label={label}
          placeholder="Type a brand name"
          autoComplete="off"
          value={query}
          onChange={(event) => onChange(event.target.value)}
          className="pl-9"
        />
      </div>
      {message && <p className="text-sm text-muted-foreground">{message}</p>}
      {options.length > 0 && (
        <ul className="divide-y overflow-hidden rounded-lg border">
          {options.map((option) => (
            <li key={option.brand_id}>
              <button
                type="button"
                onClick={() => {
                  onPick(option);
                  setQuery("");
                  setOptions([]);
                }}
                className="w-full px-3 py-2 text-left text-sm hover:bg-muted/60 focus-visible:bg-muted/60 focus-visible:outline-none"
              >
                <span className="font-medium">{option.name}</span>{" "}
                <span className="text-muted-foreground">
                  {option.strength} {option.dosage_form} · {option.manufacturer}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
