import type { Metadata } from "next";
import Link from "next/link";

import { BackLink } from "@/components/back-link";
import { Disclaimer } from "@/components/disclaimer";
import { ShareActions } from "@/components/share/share-actions";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import type { Dict } from "@/i18n/dictionaries";
import { getDict, getLang } from "@/i18n/server";
import { api, type AlternativesResponse, type RankedAlternative } from "@/lib/api";
import { rankingHref } from "@/lib/format";
import { picks, totals } from "@/lib/prescription-cost";
import { monthlyCost, parseQuantity, QUANTITY_PARAM, quantityUnit } from "@/lib/savings";
import { parseShareItems, SHARE_PARAM, type ShareItem } from "@/lib/share";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getDict();
  // A personal medicine list: keep it out of search engines.
  return { title: t.share.pageTitle, robots: { index: false, follow: false } };
}

type Row = { item: ShareItem; data: AlternativesResponse; quantity: number | null };

async function loadRow(item: ShareItem, lang: Awaited<ReturnType<typeof getLang>>): Promise<Row | null> {
  try {
    const data =
      item.kind === "brand"
        ? await api.alternatives(item.ref, lang)
        : await api.genericRanking(item.genericId, item.strength, item.dosageForm, lang);
    // Re-check the quantity against the real dosage form (e.g. bottles a month for suspensions).
    const quantity =
      item.quantity === null ? null : parseQuantity(String(item.quantity), quantityUnit(data.dosage_form));
    return { item, data, quantity };
  } catch {
    return null; // unknown or removed medicine: leave it out of the list
  }
}

function medicineName(data: AlternativesResponse, t: Dict): string {
  const name = data.alternatives.find((a) => a.is_selected)?.name ?? data.generic.name;
  return `${name} ${data.strength} ${t.fmt.form(data.dosage_form)}`;
}

function fullRankingHref(row: Row): string {
  const base =
    row.item.kind === "brand"
      ? `/alternatives/${row.data.selected_brand_code ?? row.item.ref}`
      : rankingHref(row.data.generic.id, row.data.strength, row.data.dosage_form);
  if (row.quantity === null) return base;
  return `${base}${base.includes("?") ? "&" : "?"}${QUANTITY_PARAM}=${row.quantity}`;
}

function BrandLine({ label, brand, row, t, highlight }: {
  label: string;
  brand: RankedAlternative;
  row: Row;
  t: Dict;
  highlight?: boolean;
}) {
  const unit = quantityUnit(row.data.dosage_form);
  return (
    <div className={highlight ? "rounded-lg bg-primary/5 p-2" : "p-2"}>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="space-y-0.5">
        <p>
          <strong className="font-medium">{brand.name}</strong>{" "}
          <span className="text-muted-foreground">
            ·{" "}
            <Link href={`/manufacturers/${brand.manufacturer.id}`} className="underline-offset-4 hover:underline">
              {brand.manufacturer.name}
            </Link>
          </span>
        </p>
        <p className="text-sm text-muted-foreground">
          {t.ranking.perUnit(t.fmt.price(brand.price_per_unit))} · {t.share.scoreLabel(t.fmt.score(brand.final_score))}
          {row.quantity !== null && (
            <> · {t.share.perMonth(t.fmt.taka(monthlyCost(brand.price_per_unit, row.quantity, unit)))}</>
          )}
        </p>
        {brand.manufacturer.stringent_approvals.length > 0 && (
          <div className="flex flex-wrap gap-1 pt-0.5">
            {brand.manufacturer.stringent_approvals.map((r) => (
              <Badge key={r} variant="secondary">
                {r}
              </Badge>
            ))}
          </div>
        )}
      </dd>
    </div>
  );
}

function MedicineCard({ row, t }: { row: Row; t: Dict }) {
  const p = picks(row.data);
  if (!p) return null;
  const c = t.costSummary;
  return (
    <Card className="break-inside-avoid">
      <CardHeader>
        <h2 className="font-semibold">{medicineName(row.data, t)}</h2>
        <p className="text-sm text-muted-foreground">
          {row.data.generic.name}
          {row.quantity !== null && (
            <> · {t.share.quantity(t.fmt.int(row.quantity), t.savings.unit(row.data.dosage_form))}</>
          )}
        </p>
      </CardHeader>
      <CardContent className="space-y-2">
        <dl className="grid gap-1 sm:grid-cols-2">
          {p.current && <BrandLine label={c.yourBrand} brand={p.current} row={row} t={t} />}
          {p.best !== p.current && <BrandLine label={t.share.topRanked} brand={p.best} row={row} t={t} highlight />}
          {p.cheapest !== p.best && p.cheapest !== p.current && (
            <BrandLine label={c.cheapest} brand={p.cheapest} row={row} t={t} />
          )}
        </dl>
        <Link href={fullRankingHref(row)} className="text-sm font-medium text-primary underline-offset-4 hover:underline print:hidden">
          {t.prescription.results.fullRanking}
        </Link>
      </CardContent>
    </Card>
  );
}

function Totals({ rows, t }: { rows: Row[]; t: Dict }) {
  const sum = totals(rows);
  if (sum.counted === 0) return null;
  const c = t.costSummary;
  const cell = (label: string, value: number | null) => (
    <div className="rounded-lg border p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-lg font-semibold tabular-nums">{value === null ? "–" : t.fmt.taka(value)}</p>
    </div>
  );
  return (
    <section className="space-y-2 break-inside-avoid">
      <h2 className="font-semibold">
        {t.share.totals}
        {sum.counted < rows.length && (
          <span className="font-normal text-muted-foreground"> {c.counted(sum.counted, rows.length)}</span>
        )}
      </h2>
      <div className="grid grid-cols-3 gap-2">
        {cell(c.yourBrands, sum.current)}
        {cell(c.bestBrands, sum.best)}
        {cell(c.cheapestBrands, sum.cheapest)}
      </div>
    </section>
  );
}

function shareText(rows: Row[], t: Dict): string {
  const lines = rows.flatMap((row) => {
    const p = picks(row.data);
    return p
      ? [t.share.prescriptionLine(medicineName(row.data, t), p.best.name, p.best.manufacturer.name, t.fmt.price(p.best.price_per_unit))]
      : [];
  });
  return [t.share.prescriptionIntro, ...lines, t.disclaimer].join("\n");
}

export default async function SharePage(props: PageProps<"/share">) {
  const [t, lang] = await Promise.all([getDict(), getLang()]);
  const items = parseShareItems((await props.searchParams)[SHARE_PARAM]);
  const rows = (await Promise.all(items.map((item) => loadRow(item, lang)))).filter((r) => r !== null);

  if (rows.length === 0) {
    return (
      <div className="space-y-4 py-10 text-center">
        <h1 className="text-xl font-semibold">{t.share.notFoundTitle}</h1>
        <p className="text-muted-foreground">{t.share.notFoundText}</p>
        <Link href="/" className="font-medium text-primary underline-offset-4 hover:underline">
          {t.notFound.action}
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <BackLink href="/">{t.back.newSearch}</BackLink>
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">{t.share.pageTitle}</h1>
        <p className="text-sm text-muted-foreground">{t.share.prepared(t.fmt.date(new Date()))}</p>
      </header>
      <Disclaimer />
      <ShareActions title={t.share.prescriptionTitle} text={shareText(rows, t)} />
      <ul className="space-y-3">
        {rows.map((row, i) => (
          <li key={i}>
            <MedicineCard row={row} t={t} />
          </li>
        ))}
      </ul>
      <Totals rows={rows} t={t} />
    </div>
  );
}
