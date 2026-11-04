"use client";

import { useEffect, useState } from "react";

import { InteractionResults } from "@/components/interactions/interaction-results";
import { Skeleton } from "@/components/ui/skeleton";
import { useDict } from "@/i18n/client";
import { api, isRateLimited, type InteractionCheckResponse } from "@/lib/api";

type State =
  | { status: "loading" }
  | { status: "error"; rateLimited: boolean }
  | { status: "done"; data: InteractionCheckResponse };

function parseKey(key: string): [number[], number[]] {
  const [brands, generics] = key.split("|"); // the third part is the language
  const ids = (part: string) => (part ? part.split(",").map(Number) : []);
  return [ids(brands), ids(generics)];
}

/** Fetches and shows interactions for the given medicines; re-checks when they change. */
export function InteractionPanel({ brandIds, genericIds }: { brandIds: number[]; genericIds: number[] }) {
  const t = useDict();
  const i = t.interactions;
  const [result, setResult] = useState<{ key: string; state: State }>({ key: "", state: { status: "loading" } });
  const key = `${brandIds.join(",")}|${genericIds.join(",")}|${t.lang}`;

  // Depend on the string key, not the arrays (which change identity every render).
  useEffect(() => {
    const [brand_ids, generic_ids] = parseKey(key);
    if (!brand_ids.length && !generic_ids.length) return;
    const controller = new AbortController();
    api.checkInteractions({ brand_ids, generic_ids }, controller.signal, t.lang).then(
      (data) => setResult({ key, state: { status: "done", data } }),
      (error) =>
        !controller.signal.aborted &&
        setResult({ key, state: { status: "error", rateLimited: isRateLimited(error) } }),
    );
    return () => controller.abort();
  }, [key, t.lang]);

  const state: State = result.key === key ? result.state : { status: "loading" };

  if (state.status === "loading") {
    return (
      <div aria-busy aria-label={i.checking} className="space-y-2">
        <Skeleton className="h-5 w-2/3" />
        <Skeleton className="h-16 w-full" />
      </div>
    );
  }
  if (state.status === "error") {
    return <p className="text-sm text-destructive">{state.rateLimited ? t.tooMany : i.error}</p>;
  }
  return <InteractionResults data={state.data} />;
}
