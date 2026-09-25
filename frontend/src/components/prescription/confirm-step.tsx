"use client";

import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { MedicineSearch } from "@/components/prescription/medicine-search";
import { NONE, optionKey, optionLabel, type DraftItem } from "@/components/prescription/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import type { MatchOption } from "@/lib/api";

function OptionRow({ id, value, option, extractedStrength }: {
  id: string;
  value: string;
  option: MatchOption;
  extractedStrength: string | null;
}) {
  return (
    <div className="flex items-start gap-3 rounded-lg border p-3 has-data-checked:border-primary has-data-checked:bg-primary/5">
      <RadioGroupItem id={id} value={value} className="mt-0.5" />
      <Label htmlFor={id} className="block flex-1 cursor-pointer space-y-0.5 font-normal">
        <span className="block font-medium">{optionLabel(option)}</span>
        <span className="block text-sm text-muted-foreground">
          {option.kind === "brand"
            ? `${option.generic_name} · ${option.manufacturer}`
            : "Generic name: compare all brands"}
        </span>
        {extractedStrength && !option.strength_matches && (
          <Badge variant="outline" className="mt-1 border-amber-300 bg-amber-50 text-amber-900">
            Different strength from prescription
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
          <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Read as</p>
          <p className="text-lg font-semibold">
            {item.extractedName} {item.extractedStrength}
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={onRemove} aria-label={`Remove ${item.extractedName}`}>
          <Trash2 aria-hidden />
          Remove
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {item.options.length > 0 ? (
          <>
            <p className="text-sm text-muted-foreground">Which medicine is this?</p>
            <RadioGroup
              value={item.choice}
              onValueChange={(value) => onChange({ ...item, choice: String(value) })}
              aria-label={`Match for ${item.extractedName}`}
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
                  None of these (skip this medicine)
                </Label>
              </div>
            </RadioGroup>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">
            We couldn’t find this medicine in our data. Search for it below, or remove it.
          </p>
        )}

        {searching ? (
          <MedicineSearch label={`Search for ${item.extractedName}`} onPick={addOption} />
        ) : (
          <Button variant="link" className="h-auto px-0" onClick={() => setSearching(true)}>
            Not listed? Search for it
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
        <h2 className="text-xl font-semibold">Check the medicines we found</h2>
        <p className="text-sm text-muted-foreground">
          Handwriting can be misread. Confirm each medicine before we show results.
        </p>
      </div>

      {items.length === 0 && (
        <p className="rounded-xl border p-4 text-sm text-muted-foreground">
          No medicines could be read from this photo. Try a clearer, well-lit photo, or add
          medicines by hand.
        </p>
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
          <p className="text-sm font-medium">Add a medicine</p>
          <MedicineSearch label="Add a medicine" onPick={addManual} />
        </div>
      ) : (
        <Button variant="outline" onClick={() => setAdding(true)}>
          <Plus aria-hidden />
          Add a medicine
        </Button>
      )}

      <div className="sticky bottom-0 -mx-4 space-y-2 border-t bg-background/95 px-4 py-3 backdrop-blur">
        {skipped > 0 && selected > 0 && (
          <p className="text-xs text-muted-foreground">
            {skipped} {skipped === 1 ? "medicine" : "medicines"} without a match will be skipped.
          </p>
        )}
        <div className="flex gap-2">
          <Button variant="ghost" onClick={onRestart}>
            Start over
          </Button>
          <Button className="flex-1" size="lg" disabled={selected === 0} onClick={onConfirm}>
            Show alternatives{selected > 0 ? ` for ${selected}` : ""}
          </Button>
        </div>
      </div>
    </div>
  );
}
