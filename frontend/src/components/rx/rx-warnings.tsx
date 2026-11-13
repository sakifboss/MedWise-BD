"use client";

import { Copy, HelpCircle } from "lucide-react";
import { useEffect, useState } from "react";

import { InteractionResults } from "@/components/interactions/interaction-results";
import { useDict } from "@/i18n/client";
import { api, type InteractionCheckResponse } from "@/lib/api";
import { catalogGenericIds, duplicateGenerics, type RxLine } from "@/lib/rx";

/** Information for the doctor, never blocking. The interaction call sends only generic ids. */
export function RxWarnings({ lines }: { lines: RxLine[] }) {
  const t = useDict();
  const w = t.rx.warnings;
  const ids = catalogGenericIds(lines);
  const idsKey = ids.join(",");
  const [result, setResult] = useState<{ key: string; data: InteractionCheckResponse } | null>(null);

  useEffect(() => {
    if (!idsKey || !idsKey.includes(",")) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      api
        .checkInteractions({ brand_ids: [], generic_ids: idsKey.split(",").map(Number) }, controller.signal, t.lang)
        .then((data) => setResult({ key: idsKey, data }))
        .catch(() => {});
    }, 400);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [idsKey, t.lang]);

  const duplicates = duplicateGenerics(lines);
  const unchecked = lines.filter((l) => l.source.kind === "free").map((l) => (l.source.kind === "free" ? l.source.name : ""));
  const current = result && result.key === idsKey && ids.length > 1 ? result.data : null;

  return (
    <section className="space-y-3 rounded-lg border p-3" data-testid="rx-warnings">
      <h2 className="text-sm font-semibold">{w.title}</h2>
      {duplicates.map((d) => (
        <p key={d.genericId} className="flex gap-2 text-sm text-amber-800 dark:text-amber-300">
          <Copy aria-hidden className="mt-0.5 size-4 shrink-0" />
          {w.duplicate(d.generic)}
        </p>
      ))}
      {unchecked.length > 0 && (
        <p className="flex gap-2 text-sm text-muted-foreground">
          <HelpCircle aria-hidden className="mt-0.5 size-4 shrink-0" />
          {w.notChecked(unchecked.join(", "))}
        </p>
      )}
      {ids.length < 2 ? <p className="text-sm text-muted-foreground">{w.noneYet}</p> : current && <InteractionResults data={current} />}
    </section>
  );
}
