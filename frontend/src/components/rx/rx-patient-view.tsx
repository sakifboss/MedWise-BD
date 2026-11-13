"use client";

import { AlertTriangle, BadgeCheck, CalendarPlus, Loader2, ShieldQuestion, WifiOff } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Disclaimer } from "@/components/disclaimer";
import { useMyMedicines } from "@/components/my-medicines/use-my-medicines";
import { PharmacyFinder } from "@/components/pharmacy-finder";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useDict } from "@/i18n/client";
import { api, isNetworkError, verifyRx, type BrandIndex, type GenericListItem, type RxVerifyOut } from "@/lib/api";
import { rankingHref } from "@/lib/format";
import { buildDayEventIcs } from "@/lib/ics";
import { today, upsert, type SavedMedicine } from "@/lib/my-medicines";
import { estimatedCost, formWordFor, instruction, parsePattern, type InstructionLang, type RxLine } from "@/lib/rx";
import { readRxLink, sha256Hex, type PayloadLine, type RxPayload, type RxSignature } from "@/lib/rx-payload";

type BrandInfo = BrandIndex["brands"][number];
type Read = { payload: RxPayload; text: string; signature: RxSignature };
type Check = { kind: "checking" } | { kind: "offline" } | { kind: "invalid" } | { kind: "valid"; doctor: NonNullable<RxVerifyOut["doctor"]> };

/** A payload line as an Rx line (for the shared instruction and cost functions). */
function asRxLine(line: PayloadLine, brand: BrandInfo | undefined, index: number): RxLine {
  const source: RxLine["source"] =
    line.kind === "brand" && brand
      ? {
          kind: "brand",
          code: brand.code,
          name: brand.name,
          genericId: brand.generic_id,
          generic: brand.generic,
          strength: brand.strength,
          dosageForm: brand.dosage_form,
          manufacturer: brand.manufacturer,
          pricePerUnit: brand.price_per_unit,
          priceCheckedOn: brand.price_checked_on ?? null,
          rank: brand.rank,
          groupSize: brand.group_size,
          approvals: brand.approvals,
        }
      : line.kind === "generic"
        ? { kind: "generic", genericId: 0, generic: line.generic, strength: line.strength, dosageForm: line.dosageForm }
        : { kind: "free", name: line.kind === "free" ? line.name : line.code };
  return {
    id: String(index),
    source,
    formWord: formWordFor(source.kind === "free" ? null : source.dosageForm),
    pattern: line.pattern,
    unit: line.unit,
    food: line.food,
    duration: line.duration,
    note: "",
    substitution: line.kind !== "free" && line.substitution,
  };
}

/** Units a day from the doctor's pattern, for tablets and capsules (as My Medicines expects). */
function unitsPerDay(line: PayloadLine): number | null {
  if (line.unit !== "tablet" && line.unit !== "capsule") return null;
  const slots = parsePattern(line.pattern);
  const total = slots?.reduce((a, b) => a + b, 0) ?? 0;
  return total > 0 ? total : null;
}

function download(name: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/calendar" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}

export function RxPatientView() {
  const t = useDict();
  const r = t.rxPage;
  const [read, setRead] = useState<Read | null | "broken">(null);
  const [check, setCheck] = useState<Check>({ kind: "checking" });
  const [brands, setBrands] = useState<Map<string, BrandInfo>>(new Map());
  const [generics, setGenerics] = useState<GenericListItem[]>([]);
  const [lang, setLang] = useState<InstructionLang>(t.lang);
  const [hideDoctor, setHideDoctor] = useState(false);
  const [saved, setSaved] = useState<string | null>(null);
  const { change } = useMyMedicines();

  useEffect(() => {
    // The prescription is in the part after "#", which only this page (on the device) can read.
    let active = true;
    const load = () =>
      readRxLink(window.location.hash).then(
        (value) => active && setRead(value),
        () => active && setRead("broken"),
      );
    void load();
    window.addEventListener("hashchange", load);
    api.brandIndex().then((index) => active && setBrands(new Map(index.brands.map((b) => [b.code, b])))).catch(() => {});
    api.generics().then((list) => active && setGenerics(list)).catch(() => {});
    return () => {
      active = false;
      window.removeEventListener("hashchange", load);
    };
  }, []);

  useEffect(() => {
    if (!read || read === "broken") return;
    let active = true;
    // Only the doctor id, issue time, the payload's hash and the signature are sent.
    sha256Hex(read.text)
      .then((hash) =>
        verifyRx({ doctor_id: read.signature.doctorId, issued_at: read.signature.issuedAt, hash, sig: read.signature.sig }),
      )
      .then(
        (result) => active && setCheck(result.valid && result.doctor ? { kind: "valid", doctor: result.doctor } : { kind: "invalid" }),
        (error: unknown) => active && setCheck(isNetworkError(error) || !navigator.onLine ? { kind: "offline" } : { kind: "invalid" }),
      );
    return () => {
      active = false;
    };
  }, [read]);

  if (read === null) return <Skeleton className="h-60 w-full" />;
  if (read === "broken") {
    return (
      <p className="flex gap-2 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm dark:border-amber-700 dark:bg-amber-950/40" role="alert">
        <AlertTriangle aria-hidden className="mt-0.5 size-4 shrink-0" />
        {r.broken}
      </p>
    );
  }

  const { payload, signature } = read;
  const doctorName =
    check.kind === "valid" ? (t.lang === "bn" && check.doctor.display_name_bn) || check.doctor.display_name : null;
  const issued = t.fmt.date(new Date(signature.issuedAt * 1000));
  const genericId = (name: string) => generics.find((g) => g.name === name)?.id;

  const savable: SavedMedicine[] = payload.lines.flatMap((line) => {
    const info = line.kind === "brand" ? brands.get(line.code) : undefined;
    if (!info) return [];
    return [
      {
        brandCode: info.code,
        brandName: info.name,
        genericName: info.generic,
        strength: info.strength,
        dosageForm: info.dosage_form,
        unitsPerDay: unitsPerDay(line),
        reminderTimes: [],
        addedOn: today(),
      },
    ];
  });

  return (
    <div className="space-y-5" data-testid="rx-patient-view">
      <p className="text-xs text-muted-foreground">{r.readOnDevice}</p>

      <section className="space-y-2" data-testid="rx-check">
        {check.kind === "checking" && (
          <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
            <Loader2 aria-hidden className="size-4 animate-spin" />
            {r.checking}
          </p>
        )}
        {check.kind === "valid" && doctorName && (
          <div className="space-y-1 rounded-lg border border-emerald-300 bg-emerald-50 p-3 dark:border-emerald-800 dark:bg-emerald-950/40">
            <p className="flex gap-2 text-sm font-medium">
              <BadgeCheck aria-hidden className="mt-0.5 size-4 shrink-0" />
              {r.valid(doctorName, issued)}
            </p>
            <p className="pl-6 text-xs text-muted-foreground">
              {check.doctor.degrees} · {check.doctor.specialty} · {t.rx.print.bmdc}: {check.doctor.bmdc_number}
            </p>
          </div>
        )}
        {check.kind === "valid" && check.doctor.is_demo && (
          <p className="rounded-lg border-2 border-violet-400 p-2 text-center font-semibold" data-testid="rx-demo">
            {r.demo}
          </p>
        )}
        {check.kind === "valid" && !check.doctor.is_demo && check.doctor.status !== "verified" && (
          <p className="rounded-lg border border-amber-300 bg-amber-50 p-2 text-sm dark:border-amber-700 dark:bg-amber-950/40">
            {r.notVerified}
          </p>
        )}
        {check.kind === "invalid" && (
          <p className="flex gap-2 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm dark:border-amber-700 dark:bg-amber-950/40">
            <ShieldQuestion aria-hidden className="mt-0.5 size-4 shrink-0" />
            {r.invalid}
          </p>
        )}
        {check.kind === "offline" && (
          <p className="flex gap-2 rounded-lg border p-3 text-sm">
            <WifiOff aria-hidden className="mt-0.5 size-4 shrink-0" />
            {r.offline}
          </p>
        )}
        <p className="text-sm font-medium" data-testid="rx-copy-warning">
          {r.copyWarning}
        </p>
      </section>

      <div className="flex items-center gap-2 text-sm">
        <span>{r.language}:</span>
        {(["bn", "en"] as const).map((key) => (
          <Button key={key} size="sm" variant={lang === key ? "secondary" : "outline"} aria-pressed={lang === key} onClick={() => setLang(key)}>
            {r.languages[key]}
          </Button>
        ))}
      </div>

      <ol className="space-y-3" data-testid="rx-patient-lines">
        {payload.lines.map((line, i) => {
          const brand = line.kind === "brand" ? brands.get(line.code) : undefined;
          const rx = asRxLine(line, brand, i);
          const cost = estimatedCost(rx);
          const gId = brand ? brand.generic_id : line.kind === "generic" ? genericId(line.generic) : undefined;
          const text = instruction(rx, lang);
          return (
            <li key={i} className="space-y-1 rounded-lg border p-3 text-sm">
              <p className="font-medium">
                {t.fmt.int(i + 1)}.{" "}
                {brand
                  ? `${brand.name} ${brand.strength} ${t.fmt.form(brand.dosage_form)}`
                  : line.kind === "generic"
                    ? `${line.generic} ${line.strength} ${t.fmt.form(line.dosageForm)}`
                    : line.kind === "free"
                      ? line.name
                      : line.code}
                {brand && <span className="font-normal text-muted-foreground"> ({brand.generic})</span>}
              </p>
              {line.kind === "brand" && !brand && brands.size > 0 && <p className="text-xs text-muted-foreground">{r.brandGone}</p>}
              {line.kind === "free" && <p className="text-xs text-muted-foreground">{t.rx.line.notInCatalog}</p>}
              {text && (
                <p lang={lang} data-testid="rx-patient-instruction">
                  {text}
                </p>
              )}
              {cost !== null && brand && (
                <p className="text-xs text-muted-foreground">
                  {brand.price_checked_on
                    ? t.rx.line.cost(t.fmt.price(cost), t.fmt.date(new Date(brand.price_checked_on)))
                    : t.rx.line.costNoDate(t.fmt.price(cost))}
                </p>
              )}
              {line.kind === "brand" && <p className="text-xs">{line.substitution ? t.rx.print.substitutionAllowed : t.rx.print.brandOnly}</p>}
              <p className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
                {gId && (
                  <Link href={`/generics/${gId}`} className="underline underline-offset-2">
                    {r.howToTake}
                  </Link>
                )}
                {brand && line.kind === "brand" && line.substitution && (
                  <Link href={`/alternatives/${brand.code}`} className="underline underline-offset-2">
                    {r.otherBrands}
                  </Link>
                )}
                {line.kind === "generic" && gId && (
                  <Link href={rankingHref(gId, line.strength, line.dosageForm)} className="underline underline-offset-2">
                    {r.otherBrands}
                  </Link>
                )}
              </p>
            </li>
          );
        })}
      </ol>

      <section className="space-y-2">
        <Button
          variant="outline"
          disabled={savable.length === 0}
          onClick={() => {
            const ok = change((list) => savable.reduce(upsert, list));
            setSaved(ok ? r.saved(t.fmt.int(savable.length)) : t.myMeds.unavailable);
          }}
        >
          {r.saveAll}
        </Button>
        {savable.length === 0 && brands.size > 0 && <p className="text-xs text-muted-foreground">{r.nothingToSave}</p>}
        {saved && (
          <p role="status" className="text-sm text-emerald-700 dark:text-emerald-400">
            {saved}
          </p>
        )}
      </section>

      {payload.followUp && (
        <section className="space-y-2 rounded-lg border p-3" data-testid="rx-follow-up">
          <p className="font-medium">{r.followUp(t.fmt.date(new Date(`${payload.followUp}T00:00:00`)))}</p>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="size-4" checked={hideDoctor} onChange={(e) => setHideDoctor(e.target.checked)} />
            {r.hideDoctor}
          </label>
          <Button
            variant="outline"
            size="sm"
            onClick={() =>
              download(
                "follow-up.ics",
                buildDayEventIcs(payload.followUp, hideDoctor || !doctorName ? r.followUpTitle : `${r.followUpTitle} — ${doctorName}`),
              )
            }
          >
            <CalendarPlus aria-hidden />
            {r.addToCalendar}
          </Button>
        </section>
      )}

      <PharmacyFinder />
      <Disclaimer />
    </div>
  );
}
