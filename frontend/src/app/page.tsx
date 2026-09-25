import { HowRankingWorks } from "@/components/how-ranking-works";
import { SearchBox } from "@/components/search-box";

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

      <section className="space-y-2 rounded-xl border bg-muted/30 p-4">
        <h2 className="text-sm font-semibold">How the ranking works</h2>
        <HowRankingWorks />
      </section>
    </div>
  );
}
