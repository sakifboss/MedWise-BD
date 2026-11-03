"use client";

import { Calculator } from "lucide-react";
import { useId, useState } from "react";

import { useSavings } from "@/components/savings/savings-context";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { RankedAlternative } from "@/lib/api";
import { formatTaka, monthlyCost, monthlySaving, parseQuantity } from "@/lib/savings";

const QUICK_PICKS = [1, 2, 3];

type Option = Pick<RankedAlternative, "name" | "rank" | "price_per_unit" | "is_selected">;

function SavingLine({ label, option, current }: { label: string; option: Option; current: number }) {
  const { quantity, unit } = useSavings();
  const monthly = monthlyCost(option.price_per_unit, quantity ?? 0, unit);
  const saving = monthlySaving(current, monthly);
  return (
    <p>
      {label}, <strong className="font-medium">{option.name}</strong> (rank {option.rank}):{" "}
      {formatTaka(monthly)} a month
      {saving >= 1 && (
        <>
          {" "}
          –{" "}
          <strong className="font-medium text-emerald-700">
            save {formatTaka(saving)} a month ({formatTaka(saving * 12)} a year)
          </strong>
        </>
      )}
      {saving <= -1 && <> – {formatTaka(-saving)} more a month</>}
    </p>
  );
}

function Results({ options }: { options: Option[] }) {
  const { quantity, unit, selectedPrice } = useSavings();
  if (quantity === null || options.length === 0) return null;

  const costs = options.map((o) => monthlyCost(o.price_per_unit, quantity, unit));
  if (selectedPrice === null) {
    const min = Math.min(...costs);
    const max = Math.max(...costs);
    return (
      <p className="text-sm">
        Monthly cost: {min === max ? formatTaka(min) : `${formatTaka(min)} to ${formatTaka(max)}`}
      </p>
    );
  }

  const current = monthlyCost(selectedPrice, quantity, unit);
  const best = options.find((o) => o.rank === 1);
  const cheapest = options.reduce((a, b) => (b.price_per_unit < a.price_per_unit ? b : a));
  return (
    <div className="space-y-1 text-sm">
      <p>
        Your medicine: <strong className="font-medium">{formatTaka(current)} a month</strong>
      </p>
      {best && !best.is_selected && <SavingLine label="Best ranked" option={best} current={current} />}
      {cheapest.price_per_unit < selectedPrice && cheapest !== best && (
        <SavingLine label="Cheapest" option={cheapest} current={current} />
      )}
    </div>
  );
}

export function SavingsCalculator({ options }: { options: Option[] }) {
  const { unit, quantity, setQuantity } = useSavings();
  const [draft, setDraft] = useState(quantity === null ? "" : String(quantity));
  const inputId = useId();

  function update(raw: string) {
    setDraft(raw);
    setQuantity(parseQuantity(raw, unit));
  }

  return (
    <Card>
      <CardContent className="space-y-3">
        <div className="flex items-center gap-2 font-medium">
          <Calculator aria-hidden className="size-4 text-primary" />
          Monthly cost calculator
        </div>
        <div className="space-y-2">
          <Label htmlFor={inputId}>How many {unit.label} does your prescription say?</Label>
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
              placeholder="e.g. 2"
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
                {n}
              </Button>
            ))}
          </div>
          <p className="text-xs text-muted-foreground">
            Use the number on your prescription. MedWise BD does not suggest doses.
          </p>
        </div>
        <Results options={options} />
      </CardContent>
    </Card>
  );
}

/** Monthly cost line inside a ranked card; empty until the user enters a quantity. */
export function MonthlyCost({ price, isSelected }: { price: number; isSelected: boolean }) {
  const { quantity, unit, selectedPrice } = useSavings();
  if (quantity === null) return null;

  const monthly = monthlyCost(price, quantity, unit);
  let comparison: React.ReactNode = null;
  if (isSelected) {
    comparison = <span className="text-muted-foreground">your current cost</span>;
  } else if (selectedPrice !== null) {
    const saving = monthlySaving(monthlyCost(selectedPrice, quantity, unit), monthly);
    comparison =
      saving >= 1 ? (
        <span className="font-medium text-emerald-700">save {formatTaka(saving)} a month</span>
      ) : saving <= -1 ? (
        <span className="text-muted-foreground">{formatTaka(-saving)} more a month</span>
      ) : (
        <span className="text-muted-foreground">same cost</span>
      );
  }
  return (
    <p className="text-sm">
      {formatTaka(monthly)} a month{comparison && <> · {comparison}</>}
    </p>
  );
}
