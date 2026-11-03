import type { Metadata } from "next";

import { BackLink } from "@/components/back-link";
import { PrescriptionFlow } from "@/components/prescription/prescription-flow";
import { getDict } from "@/i18n/server";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getDict();
  return { title: t.prescription.title, description: t.prescription.metaDescription };
}

export default async function PrescriptionPage() {
  const t = await getDict();
  return (
    <div className="space-y-6">
      <BackLink href="/">{t.back.byName}</BackLink>
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">{t.prescription.title}</h1>
        <p className="text-muted-foreground">{t.prescription.intro}</p>
      </header>
      <PrescriptionFlow />
    </div>
  );
}
