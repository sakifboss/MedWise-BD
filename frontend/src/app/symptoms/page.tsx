import type { Metadata } from "next";

import { BackLink } from "@/components/back-link";
import { SymptomGuide } from "@/components/symptoms/symptom-guide";
import { getDict, getLang } from "@/i18n/server";
import { api } from "@/lib/api";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getDict();
  return { title: t.symptoms.title, description: t.symptoms.metaDescription };
}

export default async function SymptomsPage() {
  const [t, lang] = await Promise.all([getDict(), getLang()]);
  const setup = await api.symptomSetup(lang);
  return (
    <div className="space-y-6">
      <BackLink href="/">{t.back.home}</BackLink>
      <h1 className="text-2xl font-semibold tracking-tight">{t.symptoms.title}</h1>
      <SymptomGuide setup={setup} />
    </div>
  );
}
