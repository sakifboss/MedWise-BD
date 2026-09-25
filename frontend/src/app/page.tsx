import { Camera, ChevronRight, ShieldAlert, type LucideIcon } from "lucide-react";
import Link from "next/link";

import { HowRankingWorks } from "@/components/how-ranking-works";
import { SearchBox } from "@/components/search-box";

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

export default function HomePage() {
  return (
    <div className="space-y-8">
      <section className="space-y-3 pt-2 sm:pt-6">
        <h1 className="text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
          Find a trusted alternative to your medicine
        </h1>
        <p className="text-muted-foreground text-pretty">
          Search a brand or generic name to see every brand with the same medicine, strength and
          form, ranked by manufacturer quality and price.
        </p>
      </section>

      <SearchBox />
      <p className="-mt-5 text-xs text-muted-foreground">
        You can type in English or Bangla, e.g. <span lang="bn">সেফিক্সিম</span>.
      </p>

      <div className="space-y-3">
        <FeatureLink
          href="/prescription"
          icon={Camera}
          title="Have a prescription?"
          text="Take a photo and we’ll find alternatives for every medicine on it."
        />
        <FeatureLink
          href="/interactions"
          icon={ShieldAlert}
          title="Taking more than one medicine?"
          text="Check them together for recorded interactions."
        />
      </div>

      <section className="space-y-2 rounded-xl border bg-muted/30 p-4">
        <h2 className="text-sm font-semibold">How the ranking works</h2>
        <HowRankingWorks />
      </section>
    </div>
  );
}
