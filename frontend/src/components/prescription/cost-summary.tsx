"use client";

import { Calculator } from "lucide-react";

import { optionKey, optionLabel } from "@/components/prescription/types";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useDict } from "@/i18n/client";
import type { AlternativesResponse, MatchOption, RankedAlternative } from "@/lib/api";
import { monthlyCost, monthlySaving, quantityUnit } from "@/lib/savings";
import { cn } from "@/lib/utils";

export type CostRow = {
  option: MatchOption;
  data: AlternativesResponse | null;
  /** Raw text the user typed; parsed by the parent. */
  draft: string;
  quantity: number | null;
};

type Picks = { current: RankedAlternative | null; best: RankedAlternative; cheapest: RankedAlternative };

function picks(data: AlternativesResponse): Picks | null {
  const [best] = data.alternatives;
  if (!best) return null;
  // Lowest price; on a tie the better-ranked brand (alternatives are already in rank order).
  const cheapest = data.alternatives.reduce((a, b) => (b.price_per_unit < a.price_per_unit ? b : a));
  return { current: data.alternatives.find((a) => a.is_selected) ?? null, best, cheapest };
}

type Totals = { current: number | null; best: number; cheapest: number; counted: number };

function totals(rows: CostRow[]): Totals {
  const result: Totals = { current: 0, best: 0, cheapest: 0, counted: 0 };
  for (const row of rows) {
    const p = row.data && picks(row.data);
    if (!p || row.quantity === null || !row.data) continue;
    const unit = quantityUnit(row.data.dosage_form);
    result.counted += 1;
    result.best += monthlyCost(p.best.price_per_unit, row.quantity, unit);
    result.cheapest += monthlyCost(p.cheapest.price_per_unit, row.quantity, unit);
    // Without a chosen brand there is no "current" cost for this medicine.
    result.current =
      p.current && result.current !== null
        ? result.current + monthlyCost(p.current.price_per_unit, row.quantity, unit)
        : null;
  }
  return result;
}

function Cost({ label, brand, monthly }: { label: string; brand: string | null; monthly: number | null }) {
  const t = useDict();
  return (
    <div className="min-w-0">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="truncate font-medium tabular-nums">{monthly === null ? "–" : t.fmt.taka(monthly)}</dd>
      {brand && <dd className="truncate text-muted-foreground">{brand}</dd>}
    </div>
  );
}

function Row({ row, onChange }: { row: CostRow; onChange: (raw: string) => void }) {
  const t = useDict();
  const c = t.costSummary;
  const p = row.data && picks(row.data);
  const unit = quantityUnit(row.option.dosage_form);
  const cost = (a: RankedAlternative | null | undefined) =>
    a && row.quantity !== null ? monthlyCost(a.price_per_unit, row.quantity, unit) : null;
  const inputId = `qty-${optionKey(row.option)}`;

  return (
    <li className="space-y-2 border-t pt-3 first:border-t-0 first:pt-0">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <label htmlFor={inputId} className="font-medium">
          {optionLabel(row.option, t)}
        </label>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Input
            id={inputId}
            type="number"
            inputMode="decimal"
            min={unit.step}
            max={unit.max}
            step={unit.step}
            value={row.draft}
            onChange={(e) => onChange(e.target.value)}
            placeholder={t.savings.placeholder}
            className="w-24"
          />
          {t.savings.unit(unit.form)}
        </div>
      </div>
      {p ? (
        <dl className="grid grid-cols-3 gap-2 text-xs">
          <Cost label={c.yourBrand} brand={p.current?.name ?? null} monthly={cost(p.current)} />
          <Cost label={c.best} brand={p.best.name} monthly={cost(p.best)} />
          <Cost label={c.cheapest} brand={p.cheapest.name} monthly={cost(p.cheapest)} />
        </dl>
      ) : (
        <p className="text-xs text-muted-foreground">{row.data ? c.noBrands : c.loading}</p>
      )}
    </li>
  );
}

function SavingNote({ current, other }: { current: number | null; other: number }) {
  const t = useDict();
  if (current === null) return null;
  const saving = monthlySaving(current, other);
  if (Math.abs(saving) < 1) return <p className="text-muted-foreground">{t.costSummary.sameAsNow}</p>;
  return saving > 0 ? (
    <p className="font-medium text-emerald-700">{t.costSummary.save(t.fmt.taka(saving), t.fmt.taka(saving * 12))}</p>
  ) : (
    <p className="text-muted-foreground">{t.costSummary.more(t.fmt.taka(-saving))}</p>
  );
}

function Tile({ title, monthly, children, highlight }: {
  title: string;
  monthly: number | null;
  children?: React.ReactNode;
  highlight?: boolean;
}) {
  const t = useDict();
  return (
    <div className={cn("space-y-0.5 rounded-lg border p-3 text-xs", highlight && "border-primary/40 bg-primary/5")}>
      <p className="text-muted-foreground">{title}</p>
      <p className="text-lg font-semibold tabular-nums">{monthly === null ? "–" : t.fmt.taka(monthly)}</p>
      {children}
    </div>
  );
}

export function CostSummary({ rows, onQuantityChange }: {
  rows: CostRow[];
  onQuantityChange: (key: string, raw: string) => void;
}) {
  const t = useDict();
  const c = t.costSummary;
  const sum = totals(rows);
  return (
    <Card>
      <CardContent className="space-y-4">
        <div className="space-y-1">
          <h3 className="flex items-center gap-2 font-semibold">
            <Calculator aria-hidden className="size-4 text-primary" />
            {c.title}
          </h3>
          <p className="text-xs text-muted-foreground">{c.note}</p>
        </div>
        <ul className="space-y-3">
          {rows.map((row) => (
            <Row key={optionKey(row.option)} row={row} onChange={(raw) => onQuantityChange(optionKey(row.option), raw)} />
          ))}
        </ul>
        {sum.counted > 0 && (
          <div className="space-y-2 border-t pt-3">
            <p className="text-sm font-medium">
              {c.total}
              {sum.counted < rows.length && (
                <span className="font-normal text-muted-foreground"> {c.counted(sum.counted, rows.length)}</span>
              )}
            </p>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
              <Tile title={c.yourBrands} monthly={sum.current}>
                {sum.current === null && <p className="text-muted-foreground">{c.pickAll}</p>}
              </Tile>
              <Tile title={c.bestBrands} monthly={sum.best} highlight>
                <SavingNote current={sum.current} other={sum.best} />
              </Tile>
              <Tile title={c.cheapestBrands} monthly={sum.cheapest}>
                <SavingNote current={sum.current} other={sum.cheapest} />
              </Tile>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
