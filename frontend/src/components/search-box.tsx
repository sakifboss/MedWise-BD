"use client";

import { ChevronRight, Loader2, Search } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { api, type SearchResponse, type SearchResult } from "@/lib/api";
import { cn } from "@/lib/utils";

const DEBOUNCE_MS = 200;

type State =
  | { status: "idle" }
  | { status: "loading"; previous?: SearchResponse }
  | { status: "done"; response: SearchResponse }
  | { status: "error" };

function resultHref(result: SearchResult): string {
  return result.type === "generic" ? `/generics/${result.id}` : `/alternatives/${result.id}`;
}

export function SearchBox() {
  const router = useRouter();
  const listId = useId();
  const [query, setQuery] = useState("");
  const [state, setState] = useState<State>({ status: "idle" });
  const [active, setActive] = useState(-1);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const inflight = useRef<AbortController | undefined>(undefined);

  useEffect(
    () => () => {
      clearTimeout(timer.current);
      inflight.current?.abort();
    },
    [],
  );

  async function runSearch(q: string) {
    inflight.current?.abort();
    const controller = new AbortController();
    inflight.current = controller;
    try {
      const response = await api.search(q, { signal: controller.signal });
      setState({ status: "done", response });
      setActive(-1);
    } catch (error) {
      if (!controller.signal.aborted) setState({ status: "error" });
      if (!(error instanceof DOMException)) console.error(error);
    }
  }

  function onChange(value: string) {
    setQuery(value);
    clearTimeout(timer.current);
    const q = value.trim();
    if (!q) {
      inflight.current?.abort();
      setState({ status: "idle" });
      return;
    }
    setState((prev) => ({
      status: "loading",
      previous: prev.status === "done" ? prev.response : prev.status === "loading" ? prev.previous : undefined,
    }));
    timer.current = setTimeout(() => void runSearch(q), DEBOUNCE_MS);
  }

  const response =
    state.status === "done" ? state.response : state.status === "loading" ? state.previous : undefined;
  const results = response?.results ?? [];

  function onKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (!results.length) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((i) => (i + 1) % results.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((i) => (i <= 0 ? results.length - 1 : i - 1));
    } else if (event.key === "Enter") {
      event.preventDefault();
      router.push(resultHref(results[Math.max(active, 0)]));
    } else if (event.key === "Escape") {
      setActive(-1);
    }
  }

  const showTransliteration =
    response && response.interpreted_as.toLowerCase() !== response.query.trim().toLowerCase();

  return (
    <div className="space-y-3">
      <div className="relative">
        <label htmlFor={`${listId}-input`} className="sr-only">
          Search for a medicine
        </label>
        <Search
          aria-hidden
          className="pointer-events-none absolute top-1/2 left-3.5 size-5 -translate-y-1/2 text-muted-foreground"
        />
        <Input
          id={`${listId}-input`}
          type="search"
          role="combobox"
          aria-expanded={results.length > 0}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={active >= 0 ? `${listId}-${active}` : undefined}
          autoComplete="off"
          autoFocus
          value={query}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Brand or generic name, e.g. Pyrolin"
          className="h-12 rounded-xl pr-10 pl-11 text-base shadow-sm"
        />
        {state.status === "loading" && (
          <Loader2
            aria-label="Searching"
            className="absolute top-1/2 right-3.5 size-5 -translate-y-1/2 animate-spin text-muted-foreground"
          />
        )}
      </div>

      <div aria-live="polite" className="text-sm text-muted-foreground">
        {state.status === "error" && (
          <p className="text-destructive">Search is unavailable right now. Please try again.</p>
        )}
        {state.status === "done" && results.length === 0 && (
          <p>
            No medicines found for “{state.response.query}”. Check the spelling or try the generic
            name.
          </p>
        )}
        {showTransliteration && results.length > 0 && (
          <p>
            Showing results for “<span className="font-medium text-foreground">{response.interpreted_as}</span>”
          </p>
        )}
      </div>

      {results.length > 0 && (
        <ul
          id={listId}
          role="listbox"
          aria-label="Search results"
          className="divide-y overflow-hidden rounded-xl border bg-card shadow-sm"
        >
          {results.map((result, index) => (
            <li
              key={`${result.type}-${result.id}`}
              id={`${listId}-${index}`}
              role="option"
              aria-selected={index === active}
            >
              <Link
                href={resultHref(result)}
                className={cn(
                  "flex items-center gap-3 px-4 py-3 transition-colors hover:bg-muted/60 focus-visible:bg-muted/60 focus-visible:outline-none",
                  index === active && "bg-muted/60",
                )}
              >
                <ResultText result={result} />
                <ChevronRight aria-hidden className="ml-auto size-4 shrink-0 text-muted-foreground" />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ResultText({ result }: { result: SearchResult }) {
  if (result.type === "generic") {
    return (
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium">{result.name}</span>
          <Badge variant="secondary">Generic</Badge>
        </div>
        <p className="text-sm text-muted-foreground">All brands, uses and interactions</p>
      </div>
    );
  }
  return (
    <div className="min-w-0">
      <p className="font-medium">
        {result.name}{" "}
        <span className="font-normal text-muted-foreground">
          {result.strength} {result.dosage_form}
        </span>
      </p>
      <p className="truncate text-sm text-muted-foreground">
        {result.generic_name} · {result.manufacturer}
      </p>
    </div>
  );
}
