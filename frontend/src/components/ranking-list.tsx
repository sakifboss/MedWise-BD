import { MonthlyCost, SavingsCalculator } from "@/components/savings/savings-calculator";
import { SavingsProvider } from "@/components/savings/savings-context";
import { RankingShare } from "@/components/share/ranking-share";
import { ScoreBar } from "@/components/score-bar";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import type { Dict } from "@/i18n/dictionaries";
import { getDict } from "@/i18n/server";
import type { AlternativesResponse, RankedAlternative } from "@/lib/api";
import { cn } from "@/lib/utils";

const BREAKDOWN: { key: keyof RankedAlternative["quality_breakdown"]; inverted?: boolean }[] = [
  { key: "certification" },
  { key: "export" },
  { key: "compliance" },
  { key: "recall_history", inverted: true },
  { key: "market" },
];

function pct(value: number): number {
  return Math.round(value * 100);
}

function Summary({ data, t }: { data: AlternativesResponse; t: Dict }) {
  const total = data.alternatives.length;
  const selected = data.alternatives.find((a) => a.is_selected);
  let text: string;
  if (total === 1) {
    text = t.ranking.onlyOne;
  } else if (!selected) {
    text = t.ranking.compared(total);
  } else if (selected.rank === 1) {
    text = t.ranking.selectedTop(selected.name, total);
  } else {
    text = t.ranking.above(selected.rank - 1, selected.name, total);
  }
  return <p className="text-sm text-muted-foreground">{text}</p>;
}

function ScoreDetails({ item, t }: { item: RankedAlternative; t: Dict }) {
  return (
    <details className="group rounded-lg border bg-muted/30 px-3 py-2 text-sm print:hidden">
      <summary className="cursor-pointer font-medium select-none">{t.ranking.howCalculated}</summary>
      <dl className="mt-3 space-y-2">
        <div className="flex justify-between gap-2">
          <dt>{t.ranking.qualityWeight}</dt>
          <dd className="tabular-nums">{t.fmt.int(pct(item.quality_score))}/{t.fmt.int(100)}</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>{t.ranking.priceWeight}</dt>
          <dd className="tabular-nums">{t.fmt.int(pct(item.price_score))}/{t.fmt.int(100)}</dd>
        </div>
      </dl>
      <p className="mt-3 mb-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">
        {t.ranking.qualityFactors}
      </p>
      <dl className="space-y-2">
        {BREAKDOWN.map(({ key, inverted }) => (
          <div key={key} className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1">
            <dt>{t.ranking.factors[key]}</dt>
            <dd className="tabular-nums">{t.fmt.int(pct(item.quality_breakdown[key]))}%</dd>
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

function Sources({ urls, t }: { urls: string[]; t: Dict }) {
  if (urls.length === 0) return null;
  return (
    <details className="rounded-lg border px-3 py-2 text-sm print:hidden">
      <summary className="cursor-pointer font-medium select-none">
        {t.ranking.sources(urls.length)}
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

function RankedCard({ item, t }: { item: RankedAlternative; t: Dict }) {
  return (
    <Card className={cn("break-inside-avoid", item.is_selected && "ring-2 ring-primary")}>
      <CardHeader className="flex flex-row items-start gap-3">
        <div
          aria-label={t.ranking.rank(item.rank)}
          className={cn(
            "flex size-9 shrink-0 items-center justify-center rounded-full bg-muted text-sm font-semibold tabular-nums",
            item.rank === 1 && "bg-primary text-primary-foreground",
          )}
        >
          {t.fmt.int(item.rank)}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-base font-semibold">{item.name}</h3>
            {item.is_selected && <Badge>{t.ranking.yourMedicine}</Badge>}
          </div>
          <p className="text-sm text-muted-foreground">{item.manufacturer.name}</p>
          {item.manufacturer.stringent_approvals.length > 0 && (
            <div className="mt-1 flex flex-wrap gap-1" aria-label={t.ranking.approvals}>
              {item.manufacturer.stringent_approvals.map((regulator) => (
                <Badge key={regulator} variant="secondary">
                  {regulator}
                </Badge>
              ))}
            </div>
          )}
          <p className="mt-1 text-sm font-medium">
            {t.ranking.perUnit(t.fmt.price(item.price_per_unit))}
            {item.price_source_url && (
              <a
                href={item.price_source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="ml-2 text-xs font-normal text-primary underline underline-offset-2"
              >
                {t.ranking.priceSource}
              </a>
            )}
          </p>
          <MonthlyCost price={item.price_per_unit} isSelected={item.is_selected} />
        </div>
        <div className="text-right">
          <p className="text-2xl leading-none font-semibold tabular-nums">{t.fmt.score(item.final_score)}</p>
          <p className="text-xs text-muted-foreground">{t.ranking.outOf100}</p>
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
        <ScoreDetails item={item} t={t} />
        <Sources urls={item.manufacturer.source_urls} t={t} />
      </CardContent>
    </Card>
  );
}

/** Plain-text summary for sharing: the top three brands, the user's own if lower, the disclaimer. */
function shareText(data: AlternativesResponse, title: string, t: Dict): string {
  const line = (a: RankedAlternative) =>
    t.share.rankingLine(
      t.fmt.int(a.rank),
      a.name,
      a.manufacturer.name,
      t.fmt.price(a.price_per_unit),
      t.fmt.score(a.final_score),
    );
  const top = data.alternatives.slice(0, 3);
  const selected = data.alternatives.find((a) => a.is_selected);
  const lines = [t.share.rankingIntro(title), ...top.map(line)];
  if (selected && selected.rank > 3) lines.push(t.share.yourMedicineLine(selected.name, t.fmt.int(selected.rank)));
  return [...lines, t.disclaimer].join("\n");
}

export async function RankingList({ data, shareTitle }: { data: AlternativesResponse; shareTitle: string }) {
  const t = await getDict();
  const selected = data.alternatives.find((a) => a.is_selected);
  const options = data.alternatives.map(({ name, rank, price_per_unit, is_selected }) => ({
    name,
    rank,
    price_per_unit,
    is_selected,
  }));
  return (
    <SavingsProvider dosageForm={data.dosage_form} selectedPrice={selected?.price_per_unit ?? null}>
      <section aria-label={t.ranking.listLabel} className="space-y-3">
        <RankingShare title={shareTitle} text={shareText(data, shareTitle, t)} />
        <SavingsCalculator options={options} />
        <Summary data={data} t={t} />
        <ol className="space-y-3">
          {data.alternatives.map((item) => (
            <li key={item.brand_id}>
              <RankedCard item={item} t={t} />
            </li>
          ))}
        </ol>
      </section>
    </SavingsProvider>
  );
}
