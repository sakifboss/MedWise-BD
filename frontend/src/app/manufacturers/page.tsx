import { ChevronRight } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { BackLink } from "@/components/back-link";
import { Badge } from "@/components/ui/badge";
import { getDict } from "@/i18n/server";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getDict();
  return { title: t.manufacturer.listTitle, description: t.manufacturer.listIntro };
}

export default async function ManufacturersPage() {
  const [list, t] = await Promise.all([api.manufacturers(), getDict()]);
  const c = t.manufacturer;

  return (
    <div className="space-y-6">
      <BackLink href="/">{t.back.home}</BackLink>
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">{c.listTitle}</h1>
        <p className="text-muted-foreground">{c.listIntro}</p>
      </header>
      <ol className="space-y-2">
        {list.map((m) => (
          <li key={m.id}>
            <Link
              href={`/manufacturers/${m.id}`}
              className="flex items-center gap-3 rounded-xl border p-3 transition-colors hover:bg-muted/50"
            >
              <span
                className={cn(
                  "flex size-9 shrink-0 items-center justify-center rounded-full bg-muted text-sm font-semibold tabular-nums",
                  m.quality_rank === 1 && "bg-primary text-primary-foreground",
                )}
              >
                {t.fmt.int(m.quality_rank)}
              </span>
              <span className="min-w-0 flex-1 space-y-1">
                <span className="block font-medium">{m.name}</span>
                {m.stringent_approvals.length > 0 && (
                  <span className="flex flex-wrap gap-1">
                    {m.stringent_approvals.map((r) => (
                      <Badge key={r} variant="secondary">
                        {r}
                      </Badge>
                    ))}
                  </span>
                )}
                <span className="block text-xs text-muted-foreground">{c.brandCount(m.brand_count)}</span>
              </span>
              <span className="shrink-0 text-right">
                <span className="block text-xl leading-none font-semibold tabular-nums">
                  {t.fmt.score(m.quality_score)}
                </span>
                <span className="block text-xs text-muted-foreground">{c.outOf100}</span>
              </span>
              <ChevronRight aria-hidden className="size-4 shrink-0 text-muted-foreground" />
            </Link>
          </li>
        ))}
      </ol>
    </div>
  );
}
