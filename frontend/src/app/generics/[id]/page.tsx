import { ChevronRight } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { BackLink } from "@/components/back-link";
import { Disclaimer } from "@/components/disclaimer";
import { SeverityBadge } from "@/components/severity-badge";
import type { Dict } from "@/i18n/dictionaries";
import { getDict, getLang } from "@/i18n/server";
import { api, isNotFound, type GenericDetail } from "@/lib/api";
import { capitalize, parseId, rankingHref } from "@/lib/format";

async function load(idParam: string) {
  const id = parseId(idParam);
  if (id === null) notFound();
  try {
    return await api.generic(id, await getLang());
  } catch (error) {
    if (isNotFound(error)) notFound();
    throw error;
  }
}

export async function generateMetadata(props: PageProps<"/generics/[id]">): Promise<Metadata> {
  const [generic, t] = await Promise.all([load((await props.params).id), getDict()]);
  return { title: generic.name, description: t.generic.metaDescription(generic.name, generic.drug_class) };
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-2">
      <h2 className="text-lg font-semibold">{title}</h2>
      {children}
    </section>
  );
}

function BulletList({ items, empty }: { items: string[]; empty: string }) {
  if (!items.length) return <p className="text-sm text-muted-foreground">{empty}</p>;
  return (
    <ul className="list-disc space-y-1 pl-5 text-sm marker:text-muted-foreground">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

function Presentations({ generic, t }: { generic: GenericDetail; t: Dict }) {
  if (!generic.presentations.length) {
    return <p className="text-sm text-muted-foreground">{t.generic.noBrands}</p>;
  }
  return (
    <ul className="divide-y overflow-hidden rounded-xl border bg-card">
      {generic.presentations.map((p) => (
        <li key={`${p.strength}-${p.dosage_form}`}>
          <Link
            href={rankingHref(generic.id, p.strength, p.dosage_form)}
            className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-muted/60"
          >
            <div className="min-w-0">
              <p className="font-medium">
                {p.strength} {t.fmt.form(p.dosage_form)}
              </p>
              <p className="text-sm text-muted-foreground">
                {t.generic.brandCount(p.brand_count)} ·{" "}
                {t.generic.perUnit(t.fmt.priceRange(p.min_price, p.max_price))}
              </p>
            </div>
            <span className="ml-auto flex shrink-0 items-center gap-1 text-sm font-medium text-primary">
              {t.generic.compareAction}
              <ChevronRight aria-hidden className="size-4" />
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

function Interactions({ generic, t }: { generic: GenericDetail; t: Dict }) {
  const localForms = generic.interactions_not_shown_forms;
  if (localForms.length) {
    // The catalog lists this generic only in local forms; DDInter is for it taken by mouth or injection.
    return (
      <p className="text-sm text-muted-foreground" data-testid="interactions-not-shown">
        {t.interactions.notShown(generic.name, localForms.map((f) => t.fmt.form(f)))}
      </p>
    );
  }
  if (!generic.interactions.length) {
    return <p className="text-sm text-muted-foreground">{t.generic.noInteractions}</p>;
  }
  return (
    <ul className="space-y-3">
      {generic.interactions.map((i) => (
        <li key={i.generic_id} className="space-y-1 rounded-lg border p-3">
          <div className="flex flex-wrap items-center gap-2">
            <Link
              href={`/generics/${i.generic_id}`}
              className="font-medium underline-offset-4 hover:underline"
            >
              {i.generic_name}
            </Link>
            <SeverityBadge severity={i.severity} />
          </div>
          <p className="text-sm text-muted-foreground">{i.description}</p>
        </li>
      ))}
    </ul>
  );
}

export default async function GenericPage(props: PageProps<"/generics/[id]">) {
  const [generic, t] = await Promise.all([load((await props.params).id), getDict()]);

  return (
    <div className="space-y-8">
      <div className="space-y-4">
        <BackLink href="/">{t.back.newSearch}</BackLink>
        <header className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">{generic.name}</h1>
          <p className="text-muted-foreground">{capitalize(generic.drug_class)}</p>
        </header>
      </div>

      <Section title={t.generic.compare}>
        <Presentations generic={generic} t={t} />
      </Section>
      {t.generic.englishOnly && generic.translation_pending.length > 0 && (
        <p className="rounded-lg border bg-muted/30 px-3 py-2 text-sm text-muted-foreground">{t.generic.englishOnly}</p>
      )}
      <Section title={t.generic.usedFor}>
        <BulletList items={generic.indications} empty={t.generic.notRecorded} />
      </Section>
      <Section title={t.generic.sideEffects}>
        <BulletList items={generic.side_effects} empty={t.generic.notRecorded} />
      </Section>
      <Section title={t.generic.precautions}>
        <BulletList items={generic.precautions} empty={t.generic.notRecorded} />
      </Section>
      {/* Only what the source says about food, milk, alcohol and timing; hidden when it says nothing. */}
      {generic.how_to_take.length > 0 && (
        <Section title={t.generic.howToTake}>
          <BulletList items={generic.how_to_take} empty={t.generic.notRecorded} />
        </Section>
      )}
      {generic.source_urls.length > 0 && (
        <p className="text-xs text-muted-foreground">
          {t.generic.sourceBefore}
          {generic.source_urls.map((url, i) => (
            <span key={url}>
              {i > 0 && ", "}
              <a href={url} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2">
                {new URL(url).hostname.replace(/^www\./, "")}
              </a>
            </span>
          ))}
          {t.lang === "bn" && generic.translation_pending.length === 0
            ? t.generic.sourceAfterTranslated
            : t.generic.sourceAfter}
        </p>
      )}
      <Section title={t.generic.interactions}>
        <Interactions generic={generic} t={t} />
        <Link
          href={`/interactions?g=${generic.id}`}
          className="inline-flex items-center gap-1 text-sm font-medium text-primary underline-offset-4 hover:underline"
        >
          {t.generic.checkWith(generic.name)}
          <ChevronRight aria-hidden className="size-4" />
        </Link>
      </Section>

      <Disclaimer />
    </div>
  );
}
