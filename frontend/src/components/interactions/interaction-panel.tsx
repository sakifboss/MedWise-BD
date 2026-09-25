"use client";

import { useEffect, useState } from "react";

import { InteractionResults } from "@/components/interactions/interaction-results";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type InteractionCheckResponse } from "@/lib/api";

type State =
  | { status: "loading" }
  | { status: "error" }
  | { status: "done"; data: InteractionCheckResponse };

function parseKey(key: string): [number[], number[]] {
  const [brands, generics] = key.split("|");
  const ids = (part: string) => (part ? part.split(",").map(Number) : []);
  return [ids(brands), ids(generics)];
}

/** Fetches and shows interactions for the given medicines; re-checks when they change. */
export function InteractionPanel({ brandIds, genericIds }: { brandIds: number[]; genericIds: number[] }) {
  const [result, setResult] = useState<{ key: string; state: State }>({ key: "", state: { status: "loading" } });
  const key = `${brandIds.join(",")}|${genericIds.join(",")}`;

  // Depend on the string key, not the arrays (which change identity every render).
  useEffect(() => {
    const [brand_ids, generic_ids] = parseKey(key);
    if (!brand_ids.length && !generic_ids.length) return;
    const controller = new AbortController();
    api.checkInteractions({ brand_ids, generic_ids }, controller.signal).then(
      (data) => setResult({ key, state: { status: "done", data } }),
      () => !controller.signal.aborted && setResult({ key, state: { status: "error" } }),
    );
    return () => controller.abort();
  }, [key]);

  const state: State = result.key === key ? result.state : { status: "loading" };

  if (state.status === "loading") {
    return (
      <div aria-busy aria-label="Checking interactions" className="space-y-2">
        <Skeleton className="h-5 w-2/3" />
        <Skeleton className="h-16 w-full" />
      </div>
    );
  }
  if (state.status === "error") {
    return <p className="text-sm text-destructive">Couldn’t check interactions right now. Please try again.</p>;
  }
  return <InteractionResults data={state.data} />;
}
