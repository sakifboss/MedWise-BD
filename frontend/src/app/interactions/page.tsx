import type { Metadata } from "next";

import { BackLink } from "@/components/back-link";
import { Disclaimer } from "@/components/disclaimer";
import { InteractionChecker, type PickedMedicine } from "@/components/interactions/interaction-checker";
import { api } from "@/lib/api";
import { parseId } from "@/lib/format";

export const metadata: Metadata = {
  title: "Interaction checker",
  description: "Check medicines together for interactions recorded in the MedWise database.",
};

/** `?g=<generic id>` (repeatable) pre-fills the checker, e.g. from a generic's page. */
async function initialMedicines(g: string | string[] | undefined): Promise<PickedMedicine[]> {
  const ids = [g ?? []].flat().map(parseId).filter((id): id is number => id !== null).slice(0, 5);
  const generics = await Promise.all(ids.map((id) => api.generic(id).catch(() => null)));
  return generics
    .filter((generic) => generic !== null)
    .map((generic) => ({ kind: "generic", id: generic.id, label: generic.name, detail: "Generic" }));
}

export default async function InteractionsPage(props: PageProps<"/interactions">) {
  const initial = await initialMedicines((await props.searchParams).g);

  return (
    <div className="space-y-6">
      <BackLink href="/">Home</BackLink>
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Interaction checker</h1>
        <p className="text-muted-foreground">
          Add the medicines you take. We’ll show any interactions recorded between them in our data.
        </p>
      </header>
      <Disclaimer />
      <InteractionChecker initial={initial} />
    </div>
  );
}
