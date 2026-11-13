"use client";

import { Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useDict } from "@/i18n/client";
import {
  PATTERN_SHORTCUTS,
  RX_UNITS,
  estimatedCost,
  instruction,
  type Duration,
  type FoodTiming,
  type RxLine,
  type RxUnit,
} from "@/lib/rx";

const SELECT =
  "h-8 rounded-lg border border-input bg-transparent px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30";

/** Text fields of a prescription line: no autofill history, no browser spellcheck service. */
const PRIVATE = { autoComplete: "off", spellCheck: false, translate: "no" } as const;

export function lineTitle(line: RxLine): { name: string; detail: string } {
  const s = line.source;
  if (s.kind === "brand") return { name: `${line.formWord} ${s.name} ${s.strength}`.trim(), detail: s.generic };
  if (s.kind === "generic") return { name: `${line.formWord} ${s.generic} ${s.strength}`.trim(), detail: "" };
  return { name: `${line.formWord} ${s.name}`.trim(), detail: "" };
}

export function LineEditor({
  line,
  index,
  onChange,
  onRemove,
}: {
  line: RxLine;
  index: number;
  onChange: (line: RxLine) => void;
  onRemove: () => void;
}) {
  const t = useDict();
  const l = t.rx.line;
  const set = (change: Partial<RxLine>) => onChange({ ...line, ...change });
  const id = (field: string) => `rx-${line.id}-${field}`;
  const title = lineTitle(line);
  const cost = estimatedCost(line);
  const durationKind = line.duration.kind;
  const setDuration = (duration: Duration) => set({ duration });
  const en = instruction(line, "en");
  const bn = instruction(line, "bn");

  return (
    <li className="space-y-3 rounded-lg border p-3" data-testid="rx-line">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-medium">
            {t.fmt.int(index + 1)}. {title.name}
            {title.detail && <span className="font-normal text-muted-foreground"> ({title.detail})</span>}
          </p>
          {line.source.kind === "brand" && (
            <p className="text-xs text-muted-foreground">
              {line.source.manufacturer} · {t.fmt.price(line.source.pricePerUnit)} ·{" "}
              {t.rx.search.rankLine(
                t.fmt.int(line.source.rank),
                t.fmt.int(line.source.groupSize),
                t.fmt.int(line.source.approvals),
              )}
            </p>
          )}
          {line.source.kind === "free" && <p className="text-xs text-amber-700 dark:text-amber-400">{l.notInCatalog}</p>}
        </div>
        <Button variant="ghost" size="sm" onClick={onRemove} aria-label={`${l.remove} ${title.name}`}>
          <Trash2 aria-hidden />
          {l.remove}
        </Button>
      </div>

      <div className="grid gap-3 sm:grid-cols-[6rem_1fr]">
        <div className="space-y-1">
          <label htmlFor={id("form")} className="text-xs font-medium">
            {l.formWord}
          </label>
          <Input id={id("form")} value={line.formWord} maxLength={12} onChange={(e) => set({ formWord: e.target.value })} {...PRIVATE} />
        </div>
        <div className="space-y-1">
          <label htmlFor={id("pattern")} className="text-xs font-medium">
            {l.pattern}
          </label>
          <Input
            id={id("pattern")}
            value={line.pattern}
            maxLength={40}
            onChange={(e) => set({ pattern: e.target.value })}
            aria-describedby={id("pattern-hint")}
            {...PRIVATE}
          />
          <p id={id("pattern-hint")} className="text-xs text-muted-foreground">
            {l.patternHint}
          </p>
          <div className="flex flex-wrap gap-1">
            {PATTERN_SHORTCUTS.map((p) => (
              <Button
                key={p}
                type="button"
                size="xs"
                variant={line.pattern === p ? "secondary" : "outline"}
                aria-pressed={line.pattern === p}
                onClick={() => set({ pattern: p })}
              >
                {p}
              </Button>
            ))}
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1">
          <label htmlFor={id("unit")} className="block text-xs font-medium">
            {l.unit}
          </label>
          <select id={id("unit")} className={SELECT} value={line.unit} onChange={(e) => set({ unit: e.target.value as RxUnit })}>
            {RX_UNITS.map((u) => (
              <option key={u} value={u}>
                {l.units[u]}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <label htmlFor={id("food")} className="block text-xs font-medium">
            {l.food}
          </label>
          <select id={id("food")} className={SELECT} value={line.food} onChange={(e) => set({ food: e.target.value as FoodTiming })}>
            {(Object.keys(l.foods) as FoodTiming[]).map((f) => (
              <option key={f} value={f}>
                {l.foods[f]}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <label htmlFor={id("duration")} className="block text-xs font-medium">
            {l.duration}
          </label>
          <div className="flex gap-1">
            <select
              id={id("duration")}
              className={SELECT}
              value={durationKind}
              onChange={(e) => {
                const kind = e.target.value as Duration["kind"];
                setDuration(kind === "fixed" ? { kind, n: 1, unit: "days" } : { kind });
              }}
            >
              {(["none", "fixed", "continue"] as const).map((k) => (
                <option key={k} value={k}>
                  {l.durationKinds[k]}
                </option>
              ))}
            </select>
            {line.duration.kind === "fixed" && (
              <>
                <Input
                  aria-label={l.durationNumber}
                  type="number"
                  min={1}
                  max={365}
                  className="w-16"
                  value={line.duration.n}
                  onChange={(e) =>
                    line.duration.kind === "fixed" &&
                    setDuration({ ...line.duration, n: Math.max(1, Math.min(365, Number(e.target.value) || 1)) })
                  }
                  {...PRIVATE}
                />
                <select
                  aria-label={l.duration}
                  className={SELECT}
                  value={line.duration.unit}
                  onChange={(e) =>
                    line.duration.kind === "fixed" &&
                    setDuration({ ...line.duration, unit: e.target.value as "days" | "weeks" | "months" })
                  }
                >
                  {(["days", "weeks", "months"] as const).map((u) => (
                    <option key={u} value={u}>
                      {l.durationUnits[u]}
                    </option>
                  ))}
                </select>
              </>
            )}
          </div>
        </div>
      </div>

      <div className="space-y-1">
        <label htmlFor={id("note")} className="text-xs font-medium">
          {l.note}
        </label>
        <Input id={id("note")} value={line.note} maxLength={120} onChange={(e) => set({ note: e.target.value })} {...PRIVATE} />
      </div>

      {line.source.kind === "brand" && (
        <label className="flex items-start gap-2 text-sm">
          <input
            type="checkbox"
            className="mt-0.5 size-4 shrink-0"
            checked={line.substitution}
            onChange={(e) => set({ substitution: e.target.checked })}
          />
          <span>{l.substitution}</span>
        </label>
      )}

      {(en || bn) && (
        <div className="rounded-md bg-muted/60 p-2 text-sm" data-testid="rx-instruction">
          <p className="text-xs text-muted-foreground">{l.forPatient}</p>
          <p lang="bn">{bn}</p>
          <p lang="en">{en}</p>
          {cost !== null && line.source.kind === "brand" && (
            <p className="mt-1 text-xs text-muted-foreground">
              {line.source.priceCheckedOn
                ? l.cost(t.fmt.price(cost), t.fmt.date(new Date(line.source.priceCheckedOn)))
                : l.costNoDate(t.fmt.price(cost))}
            </p>
          )}
        </div>
      )}
    </li>
  );
}
