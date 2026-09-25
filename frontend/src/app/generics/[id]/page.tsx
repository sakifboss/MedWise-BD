import { ChevronRight } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { BackLink } from "@/components/back-link";
import { Disclaimer } from "@/components/disclaimer";
import { SeverityBadge } from "@/components/severity-badge";
import { api, isNotFound, type GenericDetail } from "@/lib/api";
import { capitalize, formatPriceRange, parseId, rankingHref } from "@/lib/format";

async function load(idParam: string) {
  const id = parseId(idParam);
  if (id === null) notFound();
  try {
    return await api.generic(id);
  } catch (error) {
    if (isNotFound(error)) notFound();
    throw error;
  }
}

export async function generateMetadata(props: PageProps<"/generics/[id]">): Promise<Metadata> {
  const generic = await load((await props.params).id);
  return { title: generic.name, description: `${generic.name} (${generic.drug_class}): brands, uses and interactions.` };
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

function Presentations({ generic }: { generic: GenericDetail }) {
  if (!generic.presentations.length) {
    return <p className="text-sm text-muted-foreground">No brands of this medicine are in our data yet.</p>;
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
                {p.strength} {p.dosage_form}
              </p>
              <p className="text-sm text-muted-foreground">
                {p.brand_count} {p.brand_count === 1 ? "brand" : "brands"} ·{" "}
                {formatPriceRange(p.min_price, p.max_price)} per unit
              </p>
            </div>
            <span className="ml-auto flex shrink-0 items-center gap-1 text-sm font-medium text-primary">
              Compare
              <ChevronRight aria-hidden className="size-4" />
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

function Interactions({ generic }: { generic: GenericDetail }) {
  if (!generic.interactions.length) {
    return <p className="text-sm text-muted-foreground">No interactions are recorded in our data.</p>;
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
  const generic = await load((await props.params).id);

  return (
    <div className="space-y-8">
      <div className="space-y-4">
        <BackLink href="/">New search</BackLink>
        <header className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">{generic.name}</h1>
          <p className="text-muted-foreground">{capitalize(generic.drug_class)}</p>
        </header>
      </div>

      <Section title="Compare brands">
        <Presentations generic={generic} />
      </Section>
      <Section title="Used for">
        <BulletList items={generic.indications} empty="Not recorded." />
      </Section>
      <Section title="Possible side effects">
        <BulletList items={generic.side_effects} empty="Not recorded." />
      </Section>
      <Section title="Precautions">
        <BulletList items={generic.precautions} empty="Not recorded." />
      </Section>
      <Section title="Interactions">
        <Interactions generic={generic} />
      </Section>

      <Disclaimer />
    </div>
  );
}
