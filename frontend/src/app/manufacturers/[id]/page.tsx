import { CircleCheck, CircleX, ExternalLink } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { BackLink } from "@/components/back-link";
import { Disclaimer } from "@/components/disclaimer";
import { ScoreBar } from "@/components/score-bar";
import { Card, CardContent } from "@/components/ui/card";
import type { Dict } from "@/i18n/dictionaries";
import { getDict } from "@/i18n/server";
import { api, isNotFound, type ManufacturerDetail } from "@/lib/api";
import { parseId } from "@/lib/format";

const REGULATORS = ["US FDA", "UK MHRA", "EU GMP", "TGA Australia"];

async function load(idParam: string) {
  const id = parseId(idParam);
  if (id === null) notFound();
  try {
    return await api.manufacturer(id);
  } catch (error) {
    if (isNotFound(error)) notFound();
    throw error;
  }
}

export async function generateMetadata(props: PageProps<"/manufacturers/[id]">): Promise<Metadata> {
  const [m, t] = await Promise.all([load((await props.params).id), getDict()]);
  return {
    title: m.name,
    description: `${t.manufacturer.qualityScore}: ${t.fmt.score(m.quality_score)}/100 · ${m.stringent_approvals.join(", ")}`,
  };
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3 break-inside-avoid">
      <h2 className="text-lg font-semibold">{title}</h2>
      {children}
    </section>
  );
}

/** One plain sentence about the raw facts behind a factor. */
function explanation(m: ManufacturerDetail, key: ManufacturerDetail["factors"][number]["key"], t: Dict): string {
  const e = t.manufacturer.explain;
  const n = t.fmt.int;
  switch (key) {
    case "certification":
      return e.certification(n(m.stringent_approvals.length));
    case "export":
      if (m.export_country_count !== null) return e.exportKnown(n(m.export_country_count), n(m.regulated_market_exports));
      return m.regulated_market_exports > 0 ? e.exportUnknown(n(m.regulated_market_exports)) : e.exportNone;
    case "compliance":
      return e.compliance(n(m.compliance_score));
    case "recall_history":
      if (!m.recall_data_available) return e.recallUnavailable;
      return m.recall_count === 0 ? e.recallNone : e.recallCount(n(m.recall_count));
    case "market":
      return m.market_share === null
        ? e.marketUnknown(n(m.years_active))
        : e.marketKnown(m.market_share.toLocaleString(t.lang === "bn" ? "bn-BD" : "en-US"), n(m.years_active));
  }
}

function sourceLabel(url: string): string {
  try {
    const u = new URL(url);
    const path = u.pathname.length > 1 ? decodeURIComponent(u.pathname).replace(/\/$/, "") : "";
    return `${u.hostname.replace(/^www\./, "")}${path.length > 48 ? `${path.slice(0, 47)}…` : path}`;
  } catch {
    return url;
  }
}

export default async function ManufacturerPage(props: PageProps<"/manufacturers/[id]">) {
  const [m, t] = await Promise.all([load((await props.params).id), getDict()]);
  const c = t.manufacturer;

  return (
    <div className="space-y-8">
      <div className="space-y-4">
        <BackLink href="/manufacturers">{c.all}</BackLink>
        <header className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">{m.name}</h1>
          <p className="text-muted-foreground">
            {c.yearsActive(t.fmt.int(m.years_active))} · {c.brandCount(m.brands.length)}
          </p>
        </header>
      </div>

      <Card className="break-inside-avoid">
        <CardContent className="space-y-3">
          <div className="flex items-end justify-between gap-4">
            <div>
              <p className="text-sm text-muted-foreground">{c.qualityScore}</p>
              <p className="text-4xl leading-none font-semibold tabular-nums">
                {t.fmt.score(m.quality_score)}
                <span className="text-base font-normal text-muted-foreground"> / {t.fmt.int(100)}</span>
              </p>
            </div>
            <p className="text-right text-sm font-medium">
              {c.rankOf(t.fmt.int(m.quality_rank), t.fmt.int(m.manufacturer_count))}
            </p>
          </div>
          <ScoreBar value={m.quality_score} />
          <p className="text-xs text-muted-foreground">{c.scoreNote}</p>
        </CardContent>
      </Card>

      <Section title={c.approvalsTitle}>
        <ul className="grid grid-cols-2 gap-2">
          {REGULATORS.map((regulator) => {
            const ok = m.stringent_approvals.includes(regulator);
            return (
              <li
                key={regulator}
                className={ok ? "rounded-lg border border-emerald-300 bg-emerald-50 p-3 dark:border-emerald-800 dark:bg-emerald-950" : "rounded-lg border p-3"}
              >
                <p className="flex items-center gap-1.5 font-medium">
                  {ok ? (
                    <CircleCheck aria-hidden className="size-4 text-emerald-700 dark:text-emerald-300" />
                  ) : (
                    <CircleX aria-hidden className="size-4 text-muted-foreground" />
                  )}
                  {regulator}
                </p>
                <p className="text-xs text-muted-foreground">{ok ? c.approved : c.notApproved}</p>
              </li>
            );
          })}
        </ul>
        <p className="text-xs text-muted-foreground">{c.approvalsNote}</p>
      </Section>

      <Section title={c.breakdownTitle}>
        <ul className="space-y-4">
          {m.factors.map((f) => (
            <li key={f.key} className="space-y-1">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                <p className="font-medium">
                  {c.factors[f.key]}{" "}
                  <span className="text-xs font-normal text-muted-foreground">
                    ({c.weight(t.fmt.int(Math.round(f.weight * 100)))})
                  </span>
                </p>
                <p className="text-sm tabular-nums">
                  {c.points(t.fmt.score(f.points), t.fmt.int(Math.round(f.weight * 100)))}
                </p>
              </div>
              <ScoreBar value={f.score * 100} className="h-1.5" />
              <p className="text-sm text-muted-foreground">{explanation(m, f.key, t)}</p>
            </li>
          ))}
        </ul>
        <p className="border-t pt-3 text-sm font-medium">{c.total(t.fmt.score(m.quality_score))}</p>
      </Section>

      <Section title={c.unknownTitle}>
        <ul className="list-disc space-y-1 pl-5 text-sm marker:text-muted-foreground">
          {m.unknowns.map((key) => (
            <li key={key}>{c.unknown[key]}</li>
          ))}
          <li>{c.approvalsNote}</li>
        </ul>
      </Section>

      <Section title={c.brandsTitle}>
        {m.brands.length === 0 ? (
          <p className="text-sm text-muted-foreground">{c.noBrands}</p>
        ) : (
          <ul className="divide-y overflow-hidden rounded-xl border bg-card">
            {m.brands.map((b) => (
              <li key={b.id}>
                <Link
                  href={`/alternatives/${b.code}`}
                  className="flex items-center justify-between gap-3 px-4 py-2.5 transition-colors hover:bg-muted/60"
                >
                  <span className="min-w-0">
                    <span className="font-medium">{b.name}</span>{" "}
                    <span className="text-sm text-muted-foreground">
                      {b.strength} {t.fmt.form(b.dosage_form)} · {b.generic_name}
                    </span>
                  </span>
                  <span className="shrink-0 text-sm tabular-nums">{t.fmt.price(b.price_per_unit)}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title={c.sourcesTitle}>
        <p className="text-sm text-muted-foreground">{c.sourcesNote}</p>
        <ul className="space-y-1 text-sm">
          {m.source_urls.map((url) => (
            <li key={url}>
              <a
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 break-all text-primary underline underline-offset-2"
              >
                {sourceLabel(url)}
                <ExternalLink aria-hidden className="size-3 shrink-0" />
              </a>
            </li>
          ))}
        </ul>
      </Section>

      <Disclaimer />
    </div>
  );
}
