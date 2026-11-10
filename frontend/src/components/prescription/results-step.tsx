"use client";

import { ChevronRight, Trophy } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Disclaimer } from "@/components/disclaimer";
import { InteractionPanel } from "@/components/interactions/interaction-panel";
import { CostSummary } from "@/components/prescription/cost-summary";
import { optionKey, optionLabel } from "@/components/prescription/types";
import { SaveAllToMyMedicines } from "@/components/my-medicines/save-buttons";
import { ShareActions } from "@/components/share/share-actions";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useDict } from "@/i18n/client";
import type { Dict, Lang } from "@/i18n/dictionaries";
import { api, type AlternativesResponse, type MatchOption } from "@/lib/api";
import { rankingHref } from "@/lib/format";
import { picks } from "@/lib/prescription-cost";
import { parseQuantity, QUANTITY_PARAM, quantityUnit } from "@/lib/savings";
import { shareHref, shareItem } from "@/lib/share";

type Loaded = { status: "loading" } | { status: "error" } | { status: "done"; data: AlternativesResponse };

function fetchRanking(option: MatchOption, lang: Lang): Promise<AlternativesResponse> {
  return option.kind === "brand" && option.brand_id != null
    ? api.alternatives(option.brand_id, lang)
    : api.genericRanking(option.generic_id, option.strength, option.dosage_form, lang);
}

/** Link to the full ranking; carries the quantity so its cost calculator starts filled in. */
function fullRankingHref(option: MatchOption, quantity: number | null): string {
  const href =
    option.kind === "brand" && option.brand_id != null
      ? `/alternatives/${option.brand_id}`
      : rankingHref(option.generic_id, option.strength, option.dosage_form);
  if (quantity === null) return href;
  return `${href}${href.includes("?") ? "&" : "?"}${QUANTITY_PARAM}=${quantity}`;
}

/** Loads the ranking for every selected medicine once, in parallel. */
function useRankings(selections: MatchOption[], lang: Lang): Record<string, Loaded> {
  const [rankings, setRankings] = useState<Record<string, Loaded>>({});
  useEffect(() => {
    let cancelled = false;
    for (const option of selections) {
      const key = optionKey(option);
      fetchRanking(option, lang).then(
        (data) => !cancelled && setRankings((r) => ({ ...r, [key]: { status: "done", data } })),
        () => !cancelled && setRankings((r) => ({ ...r, [key]: { status: "error" } })),
      );
    }
    return () => {
      cancelled = true;
    };
  }, [selections, lang]);
  return rankings;
}

function Summary({ option, data }: { option: MatchOption; data: AlternativesResponse }) {
  const t = useDict();
  const r = t.prescription.results;
  const best = data.alternatives[0];
  const mine = data.alternatives.find((a) => a.is_selected);
  const total = data.alternatives.length;

  if (mine && mine.rank === 1) {
    return (
      <p className="text-sm">
        <strong className="font-medium">{mine.name}</strong>{" "}
        {r.alreadyTop(mine.name, total, t.fmt.score(mine.final_score))}
      </p>
    );
  }
  return (
    <div className="space-y-2 text-sm">
      {mine && (
        <p className="text-muted-foreground">
          {r.ranksOf(mine.name, mine.rank, total, t.fmt.score(mine.final_score))}
        </p>
      )}
      {!mine && option.kind === "generic" && (
        <p className="text-muted-foreground">{t.ranking.compared(total)}</p>
      )}
      <div className="flex items-start gap-2 rounded-lg bg-primary/5 p-3">
        <Trophy aria-hidden className="mt-0.5 size-4 shrink-0 text-primary" />
        <p>
          {r.topRanked} <strong className="font-medium">{best.name}</strong>
          {r.topDetail(best.manufacturer.name, t.fmt.score(best.final_score), t.fmt.price(best.price_per_unit))}
        </p>
      </div>
    </div>
  );
}

/** Message text for sharing the whole prescription (the link to /share is added separately). */
function prescriptionShareText(rows: { option: MatchOption; data: AlternativesResponse | null }[], t: Dict): string {
  // A medicine whose ranking has not loaded yet is still listed (the link has the full details).
  const lines = rows.map(({ option, data }) => {
    const p = data && picks(data);
    return p
      ? t.share.prescriptionLine(
          optionLabel(option, t),
          p.best.name,
          p.best.manufacturer.name,
          t.fmt.price(p.best.price_per_unit),
        )
      : `• ${optionLabel(option, t)}`;
  });
  return [t.share.prescriptionIntro, ...lines, t.disclaimer].join("\n");
}

function ResultCard({ option, loaded, quantity }: {
  option: MatchOption;
  loaded: Loaded;
  quantity: number | null;
}) {
  const t = useDict();
  return (
    <Card>
      <CardHeader>
        <h3 className="font-semibold">{optionLabel(option, t)}</h3>
        <p className="text-sm text-muted-foreground">{option.generic_name}</p>
      </CardHeader>
      <CardContent className="space-y-3">
        {loaded.status === "loading" && <Skeleton className="h-16 w-full" />}
        {loaded.status === "error" && (
          <p className="text-sm text-destructive">{t.prescription.results.loadError}</p>
        )}
        {loaded.status === "done" && <Summary option={option} data={loaded.data} />}
        <Link
          href={fullRankingHref(option, quantity)}
          className="inline-flex items-center gap-1 text-sm font-medium text-primary underline-offset-4 hover:underline"
        >
          {t.prescription.results.fullRanking}
          <ChevronRight aria-hidden className="size-4" />
        </Link>
      </CardContent>
    </Card>
  );
}

export function ResultsStep({
  selections,
  onBack,
  onRestart,
}: {
  selections: MatchOption[];
  onBack: () => void;
  onRestart: () => void;
}) {
  const t = useDict();
  const r = t.prescription.results;
  const rankings = useRankings(selections, t.lang);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const loadedFor = (option: MatchOption): Loaded => rankings[optionKey(option)] ?? { status: "loading" };
  const quantityFor = (option: MatchOption) =>
    parseQuantity(drafts[optionKey(option)] ?? null, quantityUnit(option.dosage_form));

  const rows = selections.map((option) => {
    const loaded = loadedFor(option);
    return {
      option,
      data: loaded.status === "done" ? loaded.data : null,
      draft: drafts[optionKey(option)] ?? "",
      quantity: quantityFor(option),
    };
  });

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">{r.heading}</h2>
      <Disclaimer />
      {selections.length > 0 && (
        <CostSummary rows={rows} onQuantityChange={(key, raw) => setDrafts((d) => ({ ...d, [key]: raw }))} />
      )}
      {selections.length > 0 && <SaveAllToMyMedicines rows={rows} />}
      {selections.length > 0 && (
        <section className="space-y-2 rounded-xl border p-4 print:hidden">
          <h3 className="font-semibold">{t.share.heading}</h3>
          <p className="text-sm text-muted-foreground">{t.share.prescriptionCardText}</p>
          <ShareActions
            title={t.share.prescriptionTitle}
            text={prescriptionShareText(rows, t)}
            url={shareHref(selections.map((option) => shareItem(option, quantityFor(option))))}
          />
        </section>
      )}
      {selections.length >= 2 && (
        <section className="space-y-2 rounded-xl border p-4">
          <h3 className="font-semibold">{r.interactions}</h3>
          <InteractionPanel
            brandIds={selections.filter((o) => o.kind === "brand").map((o) => o.brand_id!)}
            genericIds={selections.filter((o) => o.kind === "generic").map((o) => o.generic_id)}
          />
        </section>
      )}
      <h3 className="pt-2 text-lg font-semibold">{r.alternatives}</h3>
      <ul className="space-y-3">
        {selections.map((option) => (
          <li key={optionKey(option)}>
            <ResultCard option={option} loaded={loadedFor(option)} quantity={quantityFor(option)} />
          </li>
        ))}
      </ul>
      <div className="flex gap-2">
        <Button variant="ghost" onClick={onBack}>
          {r.edit}
        </Button>
        <Button variant="outline" onClick={onRestart}>
          {r.another}
        </Button>
      </div>
    </div>
  );
}
