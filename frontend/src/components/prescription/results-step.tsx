"use client";

import { ChevronRight, Trophy } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Disclaimer } from "@/components/disclaimer";
import { optionKey, optionLabel } from "@/components/prescription/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type AlternativesResponse, type MatchOption } from "@/lib/api";
import { formatPrice, rankingHref } from "@/lib/format";

type Loaded = { status: "loading" } | { status: "error" } | { status: "done"; data: AlternativesResponse };

function fetchRanking(option: MatchOption): Promise<AlternativesResponse> {
  return option.kind === "brand" && option.brand_id != null
    ? api.alternatives(option.brand_id)
    : api.genericRanking(option.generic_id, option.strength, option.dosage_form);
}

function fullRankingHref(option: MatchOption): string {
  return option.kind === "brand" && option.brand_id != null
    ? `/alternatives/${option.brand_id}`
    : rankingHref(option.generic_id, option.strength, option.dosage_form);
}

function Summary({ option, data }: { option: MatchOption; data: AlternativesResponse }) {
  const best = data.alternatives[0];
  const mine = data.alternatives.find((a) => a.is_selected);
  const total = data.alternatives.length;

  if (mine && mine.rank === 1) {
    return (
      <p className="text-sm">
        <strong className="font-medium">{mine.name}</strong> is already the top-ranked of {total}{" "}
        {total === 1 ? "brand" : "brands"} (score {mine.final_score.toFixed(1)}).
      </p>
    );
  }
  return (
    <div className="space-y-2 text-sm">
      {mine && (
        <p className="text-muted-foreground">
          {mine.name} ranks #{mine.rank} of {total} (score {mine.final_score.toFixed(1)}).
        </p>
      )}
      {!mine && option.kind === "generic" && (
        <p className="text-muted-foreground">{total} brands compared.</p>
      )}
      <div className="flex items-start gap-2 rounded-lg bg-primary/5 p-3">
        <Trophy aria-hidden className="mt-0.5 size-4 shrink-0 text-primary" />
        <p>
          Top-ranked: <strong className="font-medium">{best.name}</strong> by{" "}
          {best.manufacturer.name} · score {best.final_score.toFixed(1)} ·{" "}
          {formatPrice(best.price_per_unit)}/unit
        </p>
      </div>
    </div>
  );
}

function ResultCard({ option }: { option: MatchOption }) {
  const [loaded, setLoaded] = useState<Loaded>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    fetchRanking(option).then(
      (data) => !cancelled && setLoaded({ status: "done", data }),
      () => !cancelled && setLoaded({ status: "error" }),
    );
    return () => {
      cancelled = true;
    };
  }, [option]);

  return (
    <Card>
      <CardHeader>
        <h3 className="font-semibold">{optionLabel(option)}</h3>
        <p className="text-sm text-muted-foreground">{option.generic_name}</p>
      </CardHeader>
      <CardContent className="space-y-3">
        {loaded.status === "loading" && <Skeleton className="h-16 w-full" />}
        {loaded.status === "error" && (
          <p className="text-sm text-destructive">Couldn’t load alternatives for this medicine.</p>
        )}
        {loaded.status === "done" && <Summary option={option} data={loaded.data} />}
        <Link
          href={fullRankingHref(option)}
          className="inline-flex items-center gap-1 text-sm font-medium text-primary underline-offset-4 hover:underline"
        >
          See full ranking and reasons
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
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">Alternatives for your prescription</h2>
      <Disclaimer />
      <ul className="space-y-3">
        {selections.map((option) => (
          <li key={optionKey(option)}>
            <ResultCard option={option} />
          </li>
        ))}
      </ul>
      <div className="flex gap-2">
        <Button variant="ghost" onClick={onBack}>
          Edit medicines
        </Button>
        <Button variant="outline" onClick={onRestart}>
          Scan another prescription
        </Button>
      </div>
    </div>
  );
}
