import { Camera, ChevronRight, Factory, ShieldAlert, type LucideIcon } from "lucide-react";
import Link from "next/link";

import { HowRankingWorks } from "@/components/how-ranking-works";
import { SearchBox } from "@/components/search-box";
import { getDict } from "@/i18n/server";

function FeatureLink({
  href,
  icon: Icon,
  title,
  text,
}: {
  href: string;
  icon: LucideIcon;
  title: string;
  text: string;
}) {
  return (
    <Link
      href={href}
      className="flex items-center gap-3 rounded-xl border p-4 transition-colors hover:bg-muted/50"
    >
      <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
        <Icon aria-hidden className="size-5" />
      </span>
      <span className="min-w-0">
        <span className="block font-medium">{title}</span>
        <span className="block text-sm text-muted-foreground">{text}</span>
      </span>
      <ChevronRight aria-hidden className="ml-auto size-4 shrink-0 text-muted-foreground" />
    </Link>
  );
}

export default async function HomePage() {
  const t = await getDict();
  return (
    <div className="space-y-8">
      <section className="space-y-3 pt-2 sm:pt-6">
        <h1 className="text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
          {t.home.title}
        </h1>
        <p className="text-muted-foreground text-pretty">{t.home.intro}</p>
      </section>

      <SearchBox />
      <p className="-mt-5 text-xs text-muted-foreground">
        {t.home.typeHint} <span lang="bn">সেফিক্সিম</span>.
      </p>

      <div className="space-y-3">
        <FeatureLink
          href="/prescription"
          icon={Camera}
          title={t.home.scanTitle}
          text={t.home.scanText}
        />
        <FeatureLink
          href="/interactions"
          icon={ShieldAlert}
          title={t.home.interactionsTitle}
          text={t.home.interactionsText}
        />
        <FeatureLink
          href="/manufacturers"
          icon={Factory}
          title={t.home.companiesTitle}
          text={t.home.companiesText}
        />
      </div>

      <section className="space-y-2 rounded-xl border bg-muted/30 p-4">
        <h2 className="text-sm font-semibold">{t.home.howTitle}</h2>
        <HowRankingWorks />
      </section>
    </div>
  );
}
