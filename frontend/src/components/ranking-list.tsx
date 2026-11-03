import { ScoreBar } from "@/components/score-bar";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import type { AlternativesResponse, RankedAlternative } from "@/lib/api";
import { formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";

const BREAKDOWN: { key: keyof RankedAlternative["quality_breakdown"]; label: string; inverted?: boolean }[] = [
  { key: "certification", label: "Stringent regulator approvals" },
  { key: "export", label: "Export footprint" },
  { key: "compliance", label: "Compliance" },
  { key: "recall_history", label: "Recall history (lower is better)", inverted: true },
  { key: "market", label: "Market trust" },
];

function pct(value: number): number {
  return Math.round(value * 100);
}

function Summary({ data }: { data: AlternativesResponse }) {
  const total = data.alternatives.length;
  const selected = data.alternatives.find((a) => a.is_selected);
  let text: string;
  if (total === 1) {
    text = "No other brands with the same strength and form are in our data.";
  } else if (!selected) {
    text = `${total} brands compared.`;
  } else if (selected.rank === 1) {
    text = `${selected.name} ranks highest of the ${total} brands compared.`;
  } else {
    const above = selected.rank - 1;
    text = `${above} ${above === 1 ? "brand ranks" : "brands rank"} above ${selected.name} (${total} compared).`;
  }
  return <p className="text-sm text-muted-foreground">{text}</p>;
}

function ScoreDetails({ item }: { item: RankedAlternative }) {
  return (
    <details className="group rounded-lg border bg-muted/30 px-3 py-2 text-sm">
      <summary className="cursor-pointer font-medium select-none">How this score was calculated</summary>
      <dl className="mt-3 space-y-2">
        <div className="flex justify-between gap-2">
          <dt>Quality (80% weight)</dt>
          <dd className="tabular-nums">{pct(item.quality_score)}/100</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>Price (20% weight)</dt>
          <dd className="tabular-nums">{pct(item.price_score)}/100</dd>
        </div>
      </dl>
      <p className="mt-3 mb-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">
        Quality factors
      </p>
      <dl className="space-y-2">
        {BREAKDOWN.map(({ key, label, inverted }) => (
          <div key={key} className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1">
            <dt>{label}</dt>
            <dd className="tabular-nums">{pct(item.quality_breakdown[key])}%</dd>
            <ScoreBar
              value={pct(item.quality_breakdown[key])}
              className={cn("col-span-2 h-1.5", inverted && "[&>div]:bg-amber-500")}
            />
          </div>
        ))}
      </dl>
    </details>
  );
}

function hostname(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

function Sources({ urls }: { urls: string[] }) {
  if (urls.length === 0) return null;
  return (
    <details className="rounded-lg border px-3 py-2 text-sm">
      <summary className="cursor-pointer font-medium select-none">
        Sources for manufacturer data ({urls.length})
      </summary>
      <ul className="mt-2 space-y-1">
        {urls.map((url) => (
          <li key={url} className="truncate">
            <a href={url} target="_blank" rel="noopener noreferrer" className="text-primary underline underline-offset-2">
              {hostname(url)}
            </a>
          </li>
        ))}
      </ul>
    </details>
  );
}

function RankedCard({ item }: { item: RankedAlternative }) {
  return (
    <Card className={cn(item.is_selected && "ring-2 ring-primary")}>
      <CardHeader className="flex flex-row items-start gap-3">
        <div
          aria-label={`Rank ${item.rank}`}
          className={cn(
            "flex size-9 shrink-0 items-center justify-center rounded-full bg-muted text-sm font-semibold tabular-nums",
            item.rank === 1 && "bg-primary text-primary-foreground",
          )}
        >
          {item.rank}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-base font-semibold">{item.name}</h3>
            {item.is_selected && <Badge>Your medicine</Badge>}
          </div>
          <p className="text-sm text-muted-foreground">{item.manufacturer.name}</p>
          {item.manufacturer.stringent_approvals.length > 0 && (
            <div className="mt-1 flex flex-wrap gap-1" aria-label="Plant approvals">
              {item.manufacturer.stringent_approvals.map((regulator) => (
                <Badge key={regulator} variant="secondary">
                  {regulator}
                </Badge>
              ))}
            </div>
          )}
          <p className="mt-1 text-sm font-medium">{formatPrice(item.price_per_unit)} per unit</p>
        </div>
        <div className="text-right">
          <p className="text-2xl leading-none font-semibold tabular-nums">{item.final_score.toFixed(1)}</p>
          <p className="text-xs text-muted-foreground">out of 100</p>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <ScoreBar value={item.final_score} />
        <ul className="space-y-1 text-sm">
          {item.reasons.map((reason) => (
            <li key={reason} className="flex gap-2">
              <span aria-hidden className="mt-2 size-1.5 shrink-0 rounded-full bg-muted-foreground/60" />
              <span>{reason}</span>
            </li>
          ))}
        </ul>
        <ScoreDetails item={item} />
        <Sources urls={item.manufacturer.source_urls} />
      </CardContent>
    </Card>
  );
}

export function RankingList({ data }: { data: AlternativesResponse }) {
  return (
    <section aria-label="Ranked brands" className="space-y-3">
      <Summary data={data} />
      <ol className="space-y-3">
        {data.alternatives.map((item) => (
          <li key={item.brand_id}>
            <RankedCard item={item} />
          </li>
        ))}
      </ol>
    </section>
  );
}
