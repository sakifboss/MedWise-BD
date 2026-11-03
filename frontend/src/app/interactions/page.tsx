import type { Metadata } from "next";

import { BackLink } from "@/components/back-link";
import { Disclaimer } from "@/components/disclaimer";
import { InteractionChecker, type PickedMedicine } from "@/components/interactions/interaction-checker";
import { getDict } from "@/i18n/server";
import { api } from "@/lib/api";
import { parseId } from "@/lib/format";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getDict();
  return { title: t.interactions.title, description: t.interactions.metaDescription };
}

/** `?g=<generic id>` (repeatable) pre-fills the checker, e.g. from a generic's page. */
async function initialMedicines(g: string | string[] | undefined, detail: string): Promise<PickedMedicine[]> {
  const ids = [g ?? []].flat().map(parseId).filter((id): id is number => id !== null).slice(0, 5);
  const generics = await Promise.all(ids.map((id) => api.generic(id).catch(() => null)));
  return generics
    .filter((generic) => generic !== null)
    .map((generic) => ({ kind: "generic", id: generic.id, label: generic.name, detail }));
}

export default async function InteractionsPage(props: PageProps<"/interactions">) {
  const t = await getDict();
  const initial = await initialMedicines((await props.searchParams).g, t.interactions.generic);

  return (
    <div className="space-y-6">
      <BackLink href="/">{t.back.home}</BackLink>
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">{t.interactions.title}</h1>
        <p className="text-muted-foreground">{t.interactions.intro}</p>
      </header>
      <Disclaimer />
      <InteractionChecker initial={initial} />
    </div>
  );
}
