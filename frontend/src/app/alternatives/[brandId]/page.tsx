import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { BackLink } from "@/components/back-link";
import { Disclaimer } from "@/components/disclaimer";
import { HowRankingWorks } from "@/components/how-ranking-works";
import { RankingList } from "@/components/ranking-list";
import { getDict, getLang } from "@/i18n/server";
import { api, isNotFound } from "@/lib/api";
import { parseId } from "@/lib/format";

async function load(brandIdParam: string) {
  const brandId = parseId(brandIdParam);
  if (brandId === null) notFound();
  try {
    return await api.alternatives(brandId, await getLang());
  } catch (error) {
    if (isNotFound(error)) notFound();
    throw error;
  }
}

function selectedName(data: Awaited<ReturnType<typeof load>>): string {
  return data.alternatives.find((a) => a.is_selected)?.name ?? data.generic.name;
}

export async function generateMetadata(props: PageProps<"/alternatives/[brandId]">): Promise<Metadata> {
  const [data, t] = await Promise.all([load((await props.params).brandId), getDict()]);
  return { title: t.alternatives.title(`${selectedName(data)} ${data.strength}`) };
}

export default async function AlternativesPage(props: PageProps<"/alternatives/[brandId]">) {
  const [data, t] = await Promise.all([load((await props.params).brandId), getDict()]);

  return (
    <div className="space-y-6">
      <BackLink href="/">{t.back.newSearch}</BackLink>
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">{t.alternatives.title(selectedName(data))}</h1>
        <p className="text-muted-foreground">
          <Link href={`/generics/${data.generic.id}`} className="font-medium text-primary underline-offset-4 hover:underline">
            {data.generic.name}
          </Link>{" "}
          {data.strength} {t.fmt.form(data.dosage_form)}
        </p>
      </header>
      <Disclaimer />
      <HowRankingWorks />
      <RankingList data={data} shareTitle={t.alternatives.title(`${selectedName(data)} ${data.strength}`)} />
    </div>
  );
}
