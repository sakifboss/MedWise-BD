"use client";

import { Calculator } from "lucide-react";
import { useId, useState } from "react";

import { useSavings } from "@/components/savings/savings-context";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useDict } from "@/i18n/client";
import type { RankedAlternative } from "@/lib/api";
import { monthlyCost, monthlySaving, parseQuantity } from "@/lib/savings";
import { cn } from "@/lib/utils";

const QUICK_PICKS = [1, 2, 3];

type Option = Pick<RankedAlternative, "name" | "rank" | "price_per_unit" | "is_selected">;

function SavingLine({ label, option, current }: { label: string; option: Option; current: number }) {
  const t = useDict();
  const { quantity, unit } = useSavings();
  const monthly = monthlyCost(option.price_per_unit, quantity ?? 0, unit);
  const saving = monthlySaving(current, monthly);
  return (
    <p>
      {label}, <strong className="font-medium">{option.name}</strong> {t.savings.rank(t.fmt.int(option.rank))}:{" "}
      {t.savings.perMonth(t.fmt.taka(monthly))}
      {saving >= 1 && (
        <>
          {" "}
          –{" "}
          <strong className="font-medium text-emerald-700">
            {t.savings.save(t.fmt.taka(saving), t.fmt.taka(saving * 12))}
          </strong>
        </>
      )}
      {saving <= -1 && <> – {t.savings.more(t.fmt.taka(-saving))}</>}
    </p>
  );
}

function Results({ options }: { options: Option[] }) {
  const t = useDict();
  const { quantity, unit, selectedPrice } = useSavings();
  if (quantity === null || options.length === 0) return null;

  const costs = options.map((o) => monthlyCost(o.price_per_unit, quantity, unit));
  if (selectedPrice === null) {
    const min = Math.min(...costs);
    const max = Math.max(...costs);
    return <p className="text-sm">{t.savings.range(t.fmt.taka(min), t.fmt.taka(max))}</p>;
  }

  const current = monthlyCost(selectedPrice, quantity, unit);
  const best = options.find((o) => o.rank === 1);
  const cheapest = options.reduce((a, b) => (b.price_per_unit < a.price_per_unit ? b : a));
  return (
    <div className="space-y-1 text-sm">
      <p>
        {t.savings.yourMedicine} <strong className="font-medium">{t.savings.perMonth(t.fmt.taka(current))}</strong>
      </p>
      {best && !best.is_selected && <SavingLine label={t.savings.best} option={best} current={current} />}
      {cheapest.price_per_unit < selectedPrice && cheapest !== best && (
        <SavingLine label={t.savings.cheapest} option={cheapest} current={current} />
      )}
    </div>
  );
}

export function SavingsCalculator({ options }: { options: Option[] }) {
  const t = useDict();
  const { unit, quantity, setQuantity } = useSavings();
  const [draft, setDraft] = useState(quantity === null ? "" : String(quantity));
  const inputId = useId();

  function update(raw: string) {
    setDraft(raw);
    setQuantity(parseQuantity(raw, unit));
  }

  return (
    <Card className={cn("break-inside-avoid", quantity === null && "print:hidden")}>
      <CardContent className="space-y-3">
        <div className="flex items-center gap-2 font-medium">
          <Calculator aria-hidden className="size-4 text-primary" />
          {t.savings.title}
        </div>
        <div className="space-y-2 print:hidden">
          <Label htmlFor={inputId}>{t.savings.question(unit.form)}</Label>
          <div className="flex flex-wrap items-center gap-2">
            <Input
              id={inputId}
              type="number"
              inputMode="decimal"
              min={unit.step}
              max={unit.max}
              step={unit.step}
              value={draft}
              onChange={(e) => update(e.target.value)}
              placeholder={t.savings.placeholder}
              className="w-24"
            />
            {QUICK_PICKS.map((n) => (
              <Button
                key={n}
                type="button"
                size="sm"
                variant={quantity === n ? "default" : "outline"}
                onClick={() => update(String(n))}
              >
                {t.fmt.int(n)}
              </Button>
            ))}
          </div>
          <p className="text-xs text-muted-foreground">{t.savings.noDoseNote}</p>
        </div>
        <Results options={options} />
      </CardContent>
    </Card>
  );
}

/** Monthly cost line inside a ranked card; empty until the user enters a quantity. */
export function MonthlyCost({ price, isSelected }: { price: number; isSelected: boolean }) {
  const t = useDict();
  const { quantity, unit, selectedPrice } = useSavings();
  if (quantity === null) return null;

  const monthly = monthlyCost(price, quantity, unit);
  let comparison: React.ReactNode = null;
  if (isSelected) {
    comparison = <span className="text-muted-foreground">{t.savings.current}</span>;
  } else if (selectedPrice !== null) {
    const saving = monthlySaving(monthlyCost(selectedPrice, quantity, unit), monthly);
    comparison =
      saving >= 1 ? (
        <span className="font-medium text-emerald-700">{t.savings.saveShort(t.fmt.taka(saving))}</span>
      ) : saving <= -1 ? (
        <span className="text-muted-foreground">{t.savings.more(t.fmt.taka(-saving))}</span>
      ) : (
        <span className="text-muted-foreground">{t.savings.same}</span>
      );
  }
  return (
    <p className="text-sm">
      {t.savings.perMonth(t.fmt.taka(monthly))}
      {comparison && <> · {comparison}</>}
    </p>
  );
}
