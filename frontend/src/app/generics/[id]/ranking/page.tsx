import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { BackLink } from "@/components/back-link";
import { Disclaimer } from "@/components/disclaimer";
import { HowRankingWorks } from "@/components/how-ranking-works";
import { PharmacyFinder } from "@/components/pharmacy-finder";
import { RememberPage } from "@/components/recent/remember-page";
import { rankingHref } from "@/lib/format";
import { RankingList } from "@/components/ranking-list";
import { getDict, getLang } from "@/i18n/server";
import { api, isNotFound } from "@/lib/api";
import { parseId } from "@/lib/format";

type Props = PageProps<"/generics/[id]/ranking">;

function single(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

async function load(props: Props) {
  const id = parseId((await props.params).id);
  const query = await props.searchParams;
  const strength = single(query.strength);
  const form = single(query.form);
  if (id === null || !strength || !form) notFound();
  try {
    return await api.genericRanking(id, strength, form, await getLang());
  } catch (error) {
    if (isNotFound(error)) notFound();
    throw error;
  }
}

export async function generateMetadata(props: Props): Promise<Metadata> {
  const [data, t] = await Promise.all([load(props), getDict()]);
  return { title: t.ranking.title(data.generic.name, data.strength, t.fmt.form(data.dosage_form)) };
}

export default async function GenericRankingPage(props: Props) {
  const [data, t] = await Promise.all([load(props), getDict()]);

  return (
    <div className="space-y-6">
      <BackLink href={`/generics/${data.generic.id}`}>{data.generic.name}</BackLink>
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">
          {data.generic.name} {data.strength} {t.fmt.form(data.dosage_form)}
        </h1>
        <p className="text-muted-foreground">{t.ranking.subtitle}</p>
      </header>
      <Disclaimer />
      <HowRankingWorks />
      <RankingList
        data={data}
        shareTitle={t.ranking.title(data.generic.name, data.strength, t.fmt.form(data.dosage_form))}
      />
      <PharmacyFinder />
      <RememberPage
        item={{
          kind: "ranking",
          name: data.generic.name,
          genericName: data.generic.name,
          strength: data.strength,
          dosageForm: data.dosage_form,
          href: rankingHref(data.generic.id, data.strength, data.dosage_form),
        }}
      />
    </div>
  );
}
