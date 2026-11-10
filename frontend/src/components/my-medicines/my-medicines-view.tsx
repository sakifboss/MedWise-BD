"use client";

import { CalendarPlus, Download, ShieldCheck, Trash2, Trophy, Upload, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { Disclaimer } from "@/components/disclaimer";
import { InteractionPanel } from "@/components/interactions/interaction-panel";
import { useMyMedicines } from "@/components/my-medicines/use-my-medicines";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useDict } from "@/i18n/client";
import type { Dict } from "@/i18n/dictionaries";
import { api, type AlternativesResponse } from "@/lib/api";
import { buildIcs, reminderTitle } from "@/lib/ics";
import {
  EMPTY_LIST,
  compare,
  merge,
  parseListText,
  remove,
  update,
  type MyMedicinesList,
  type SavedMedicine,
} from "@/lib/my-medicines";
import { QUANTITY_PARAM } from "@/lib/savings";

type Loaded = { status: "loading" } | { status: "error" } | { status: "done"; data: AlternativesResponse };

/** Rankings for every saved brand, loaded once per set of brands (only brand ids are sent). */
function useRankings(brandIds: number[], lang: Dict["lang"]): Record<number, Loaded> {
  const [rankings, setRankings] = useState<Record<number, Loaded>>({});
  const key = `${brandIds.join(",")}|${lang}`;
  useEffect(() => {
    let cancelled = false;
    for (const id of key.split("|")[0].split(",").filter(Boolean).map(Number)) {
      api.alternatives(id, lang).then(
        (data) => !cancelled && setRankings((r) => ({ ...r, [id]: { status: "done", data } })),
        () => !cancelled && setRankings((r) => ({ ...r, [id]: { status: "error" } })),
      );
    }
    return () => {
      cancelled = true;
    };
  }, [key, lang]);
  return rankings;
}

function download(filename: string, type: string, text: string): void {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function Standing({ item, loaded }: { item: SavedMedicine; loaded: Loaded | undefined }) {
  const t = useDict();
  const m = t.myMeds;
  if (!loaded || loaded.status === "loading") return <Skeleton className="h-12 w-full" />;
  if (loaded.status === "error") return <p className="text-sm text-destructive">{m.loadError}</p>;
  const c = compare(item, loaded.data);
  if (!c) return <p className="text-sm text-muted-foreground">{m.notListed}</p>;
  const money = (v: number) => t.fmt.price(Math.abs(v));
  return (
    <div className="space-y-1.5 text-sm" data-testid="standing">
      <p className="font-medium">{m.rank(t.fmt.int(c.rank), t.fmt.int(c.total))}</p>
      {c.top === null ? (
        <p className="text-muted-foreground">{m.isTop}</p>
      ) : (
        <div className="flex items-start gap-2 rounded-lg bg-primary/5 p-2.5">
          <Trophy aria-hidden className="mt-0.5 size-4 shrink-0 text-primary" />
          <div>
            <p>{m.topRanked(c.top.name, c.top.manufacturer)}</p>
            {c.samePrice ? (
              <p className="text-muted-foreground">{m.samePrice}</p>
            ) : (
              c.differencePer30 !== null && (
                <p className="text-muted-foreground">
                  {m.per30(money(c.differencePer30), c.differencePer30 < 0)}
                  {c.differencePerMonth !== null &&
                    ` · ${m.perMonth(money(c.differencePerMonth), c.differencePerMonth < 0)}`}
                </p>
              )
            )}
            <p className="mt-1 font-medium">{m.askFirst}</p>
          </div>
        </div>
      )}
    </div>
  );
}

function MedicineCard({
  item,
  loaded,
  onChange,
}: {
  item: SavedMedicine;
  loaded: Loaded | undefined;
  onChange: (fn: (list: MyMedicinesList) => MyMedicinesList) => void;
}) {
  const t = useDict();
  const m = t.myMeds;
  const [time, setTime] = useState("");
  const href = `/alternatives/${item.brandId}${item.unitsPerDay ? `?${QUANTITY_PARAM}=${item.unitsPerDay}` : ""}`;
  const unitsId = `units-${item.brandId}`;
  const timeId = `time-${item.brandId}`;

  return (
    <Card data-testid="saved-medicine">
      <CardHeader className="flex flex-row items-start justify-between gap-2">
        <div>
          <h2 className="font-semibold">
            {item.brandName} {item.strength} {t.fmt.form(item.dosageForm)}
          </h2>
          <p className="text-sm text-muted-foreground">
            {item.genericName} · {m.savedOn(t.fmt.date(new Date(`${item.addedOn}T12:00:00`)))}
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={() => onChange((l) => remove(l, item.brandId))}>
          <X aria-hidden />
          {m.remove}
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        <Standing item={item} loaded={loaded} />
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor={unitsId}>{m.unitsLabel}</Label>
            <Input
              id={unitsId}
              type="number"
              inputMode="decimal"
              min={0}
              step="0.5"
              value={item.unitsPerDay ?? ""}
              onChange={(e) => {
                const v = e.target.value === "" ? null : Number(e.target.value);
                onChange((l) => update(l, item.brandId, { unitsPerDay: v }));
              }}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={timeId}>{m.remindersLabel}</Label>
            <div className="flex gap-2">
              <Input id={timeId} type="time" value={time} onChange={(e) => setTime(e.target.value)} />
              <Button
                variant="outline"
                disabled={!time}
                onClick={() => {
                  onChange((l) => update(l, item.brandId, { reminderTimes: [...item.reminderTimes, time] }));
                  setTime("");
                }}
              >
                {m.addTime}
              </Button>
            </div>
            {item.reminderTimes.length > 0 && (
              <ul className="flex flex-wrap gap-2 pt-1">
                {item.reminderTimes.map((rt) => (
                  <li key={rt} className="flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-sm tabular-nums">
                    {rt}
                    <button
                      type="button"
                      aria-label={m.removeTime(rt)}
                      className="rounded-full p-0.5 hover:bg-muted"
                      onClick={() =>
                        onChange((l) =>
                          update(l, item.brandId, { reminderTimes: item.reminderTimes.filter((x) => x !== rt) }),
                        )
                      }
                    >
                      <X aria-hidden className="size-3.5" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
        <Link href={href} className="inline-block text-sm font-medium text-primary underline-offset-4 hover:underline">
          {m.viewRanking}
        </Link>
      </CardContent>
    </Card>
  );
}

export function MyMedicinesView() {
  const t = useDict();
  const m = t.myMeds;
  const { list, available, change } = useMyMedicines();
  const rankings = useRankings(
    list.items.map((i) => i.brandId),
    t.lang,
  );
  const [hideNames, setHideNames] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const reminders = list.items.flatMap((item) =>
    item.reminderTimes.map((time) => ({ title: reminderTitle(item, hideNames, m.reminderTitle), time })),
  );

  async function importFile(file: File) {
    const imported = parseListText(await file.text());
    if (imported.items.length === 0) {
      setNotice(m.importFailed);
      return;
    }
    change((l) => merge(l, imported));
    setNotice(m.imported(t.fmt.int(imported.items.length)));
  }

  return (
    <div className="space-y-6">
      <header className="space-y-3">
        <h1 className="text-2xl font-semibold tracking-tight">{m.title}</h1>
        <Alert className="border-primary/30 bg-primary/5">
          <ShieldCheck aria-hidden />
          <AlertDescription className="font-medium text-foreground" data-testid="privacy-note">
            {m.privacy}
          </AlertDescription>
        </Alert>
      </header>

      {!available && (
        <p className="rounded-lg border border-destructive/40 p-3 text-sm" role="status" data-testid="storage-unavailable">
          {m.unavailable}
        </p>
      )}
      {notice && (
        <p aria-live="polite" className="text-sm" data-testid="notice">
          {notice}
        </p>
      )}

      {list.items.length === 0 ? (
        <p className="text-muted-foreground" data-testid="empty">
          {m.empty}
        </p>
      ) : (
        <>
          <Disclaimer />
          <ul className="space-y-3">
            {list.items.map((item) => (
              <li key={item.brandId}>
                <MedicineCard item={item} loaded={rankings[item.brandId]} onChange={change} />
              </li>
            ))}
          </ul>

          {list.items.length >= 2 && (
            <section className="space-y-2 rounded-xl border p-4">
              <h2 className="font-semibold">{m.interactions}</h2>
              <InteractionPanel brandIds={list.items.map((i) => i.brandId)} genericIds={[]} />
            </section>
          )}

          <section className="space-y-3 rounded-xl border p-4">
            <h2 className="font-semibold">{m.calendar}</h2>
            <p className="text-sm text-muted-foreground">{m.calendarNote}</p>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={hideNames} onChange={(e) => setHideNames(e.target.checked)} />
              {m.hideNames}
            </label>
            <Button
              variant="outline"
              disabled={reminders.length === 0}
              onClick={() => download("medwise-reminders.ics", "text/calendar", buildIcs(reminders))}
            >
              <CalendarPlus aria-hidden />
              {m.addToCalendar}
            </Button>
            {reminders.length === 0 && <p className="text-sm text-muted-foreground">{m.noTimes}</p>}
          </section>
        </>
      )}

      {available && (
        <section className="space-y-3 rounded-xl border p-4">
          <h2 className="font-semibold">{m.backup}</h2>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              disabled={list.items.length === 0}
              onClick={() =>
                download("medwise-my-medicines.json", "application/json", JSON.stringify(list, null, 2) + "\n")
              }
            >
              <Download aria-hidden />
              {m.download}
            </Button>
            <Button variant="outline" onClick={() => fileInput.current?.click()}>
              <Upload aria-hidden />
              {m.import}
            </Button>
            <input
              ref={fileInput}
              type="file"
              accept="application/json,.json"
              className="hidden"
              data-testid="import-file"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) void importFile(file);
                e.target.value = "";
              }}
            />
          </div>
          {list.items.length > 0 &&
            (confirming ? (
              <div className="space-y-2 rounded-lg border border-destructive/40 p-3" role="alertdialog" aria-label={m.confirmDelete}>
                <p className="text-sm font-medium">{m.confirmDelete}</p>
                <div className="flex gap-2">
                  <Button
                    variant="destructive"
                    onClick={() => {
                      change(() => EMPTY_LIST);
                      setConfirming(false);
                      setNotice(m.deleted);
                    }}
                  >
                    {m.confirmYes}
                  </Button>
                  <Button variant="ghost" onClick={() => setConfirming(false)}>
                    {m.cancel}
                  </Button>
                </div>
              </div>
            ) : (
              <Button variant="ghost" className="text-destructive" onClick={() => setConfirming(true)}>
                <Trash2 aria-hidden />
                {m.deleteAll}
              </Button>
            ))}
        </section>
      )}
    </div>
  );
}
