"use client";

import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { MedicineSearch } from "@/components/prescription/medicine-search";
import { NONE, optionKey, optionLabel, type DraftItem } from "@/components/prescription/types";
import { RequestMedicine } from "@/components/request-medicine";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { useDict } from "@/i18n/client";
import type { MatchOption } from "@/lib/api";

function OptionRow({ id, value, option, extractedStrength }: {
  id: string;
  value: string;
  option: MatchOption;
  extractedStrength: string | null;
}) {
  const t = useDict();
  return (
    <div className="flex items-start gap-3 rounded-lg border p-3 has-data-checked:border-primary has-data-checked:bg-primary/5">
      <RadioGroupItem id={id} value={value} className="mt-0.5" />
      <Label htmlFor={id} className="block flex-1 cursor-pointer space-y-0.5 font-normal">
        <span className="block font-medium">{optionLabel(option, t)}</span>
        <span className="block text-sm text-muted-foreground">
          {option.kind === "brand"
            ? `${option.generic_name} · ${option.manufacturer}`
            : t.prescription.confirm.genericOption}
        </span>
        {extractedStrength && !option.strength_matches && (
          <Badge variant="outline" className="mt-1 border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200">
            {t.prescription.confirm.differentStrength}
          </Badge>
        )}
      </Label>
    </div>
  );
}

function ItemCard({
  item,
  onChange,
  onRemove,
}: {
  item: DraftItem;
  onChange: (item: DraftItem) => void;
  onRemove: () => void;
}) {
  const [searching, setSearching] = useState(item.options.length === 0);
  const c = useDict().prescription.confirm;

  function addOption(option: MatchOption) {
    const existing = item.options.findIndex((o) => optionKey(o) === optionKey(option));
    if (existing >= 0) {
      onChange({ ...item, choice: String(existing) });
    } else {
      onChange({ ...item, options: [option, ...item.options], choice: "0" });
    }
    setSearching(false);
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{c.readAs}</p>
          <p className="text-lg font-semibold">
            {item.extractedName} {item.extractedStrength}
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={onRemove} aria-label={c.removeLabel(item.extractedName)}>
          <Trash2 aria-hidden />
          {c.remove}
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {item.options.length > 0 ? (
          <>
            <p className="text-sm text-muted-foreground">{c.which}</p>
            <RadioGroup
              value={item.choice}
              onValueChange={(value) => onChange({ ...item, choice: String(value) })}
              aria-label={c.matchLabel(item.extractedName)}
            >
              {item.options.map((option, index) => (
                <OptionRow
                  key={optionKey(option)}
                  id={`${item.key}-${index}`}
                  value={String(index)}
                  option={option}
                  extractedStrength={item.extractedStrength}
                />
              ))}
              <div className="flex items-center gap-3 rounded-lg border p-3 has-data-checked:border-primary has-data-checked:bg-primary/5">
                <RadioGroupItem id={`${item.key}-none`} value={NONE} />
                <Label htmlFor={`${item.key}-none`} className="cursor-pointer font-normal">
                  {c.none}
                </Label>
              </div>
            </RadioGroup>
          </>
        ) : (
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">{c.notFound}</p>
            <RequestMedicine key={item.extractedName} query={item.extractedName} source="prescription" />
          </div>
        )}

        {searching ? (
          <MedicineSearch label={c.searchFor(item.extractedName)} onPick={addOption} />
        ) : (
          <Button variant="link" className="h-auto px-0" onClick={() => setSearching(true)}>
            {c.notListed}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

export function ConfirmStep({
  items,
  onItemsChange,
  onConfirm,
  onRestart,
}: {
  items: DraftItem[];
  onItemsChange: (items: DraftItem[]) => void;
  onConfirm: () => void;
  onRestart: () => void;
}) {
  const [adding, setAdding] = useState(false);
  const c = useDict().prescription.confirm;
  const selected = items.filter((i) => i.choice !== NONE).length;
  const skipped = items.length - selected;

  function update(index: number, item: DraftItem) {
    onItemsChange(items.map((current, i) => (i === index ? item : current)));
  }

  function addManual(option: MatchOption) {
    const key = `manual-${Date.now()}`;
    onItemsChange([
      ...items,
      { key, extractedName: option.name, extractedStrength: option.strength, options: [option], choice: "0" },
    ]);
    setAdding(false);
  }

  return (
    <div className="space-y-4">
      <div className="space-y-1">
        <h2 className="text-xl font-semibold">{c.heading}</h2>
        <p className="text-sm text-muted-foreground">{c.intro}</p>
      </div>

      {items.length === 0 && (
        <p className="rounded-xl border p-4 text-sm text-muted-foreground">{c.noneRead}</p>
      )}

      <ul className="space-y-3">
        {items.map((item, index) => (
          <li key={item.key}>
            <ItemCard
              item={item}
              onChange={(next) => update(index, next)}
              onRemove={() => onItemsChange(items.filter((_, i) => i !== index))}
            />
          </li>
        ))}
      </ul>

      {adding ? (
        <div className="space-y-2 rounded-xl border p-4">
          <p className="text-sm font-medium">{c.add}</p>
          <MedicineSearch label={c.add} onPick={addManual} />
        </div>
      ) : (
        <Button variant="outline" onClick={() => setAdding(true)}>
          <Plus aria-hidden />
          {c.add}
        </Button>
      )}

      <div className="sticky bottom-0 -mx-4 space-y-2 border-t bg-background/95 px-4 py-3 backdrop-blur">
        {skipped > 0 && selected > 0 && (
          <p className="text-xs text-muted-foreground">{c.skipped(skipped)}</p>
        )}
        <div className="flex gap-2">
          <Button variant="ghost" onClick={onRestart}>
            {c.startOver}
          </Button>
          <Button className="flex-1" size="lg" disabled={selected === 0} onClick={onConfirm}>
            {c.show(selected)}
          </Button>
        </div>
      </div>
    </div>
  );
}
