"use client";

import { History, Trash2 } from "lucide-react";
import Link from "next/link";
import { useMemo, useSyncExternalStore } from "react";

import { Button } from "@/components/ui/button";
import { useDict } from "@/i18n/client";
import { clearRecent, parseRecent, recentSnapshot, subscribeRecent } from "@/lib/recent";

/** Home page: the last pages opened on this device. Hidden when there are none. */
export function RecentlyViewed() {
  const t = useDict();
  const r = t.recent;
  const text = useSyncExternalStore(subscribeRecent, recentSnapshot, () => "");
  const items = useMemo(() => parseRecent(text || null).items, [text]);
  if (items.length === 0) return null;

  return (
    <section className="space-y-2" aria-labelledby="recent-heading" data-testid="recently-viewed">
      <div className="flex items-center justify-between gap-2">
        <h2 id="recent-heading" className="flex items-center gap-1.5 text-sm font-semibold">
          <History aria-hidden className="size-4" />
          {r.title}
        </h2>
        <Button variant="ghost" size="sm" onClick={clearRecent} className="text-muted-foreground">
          <Trash2 aria-hidden />
          {r.clear}
        </Button>
      </div>
      <ul className="flex flex-wrap gap-2">
        {items.map((item) => (
          <li key={item.href}>
            <Link
              href={item.href}
              className="inline-flex flex-col rounded-lg border px-3 py-1.5 text-sm transition-colors hover:bg-muted/50"
              data-testid="recent-item"
            >
              <span className="font-medium">{item.name}</span>
              <span className="text-xs text-muted-foreground">
                {item.kind === "alternatives" ? `${item.genericName} ` : ""}
                {item.strength} {t.fmt.form(item.dosageForm)}
                {item.kind === "ranking" ? ` · ${r.allBrands}` : ""}
              </span>
            </Link>
          </li>
        ))}
      </ul>
      <p className="text-xs text-muted-foreground">{r.onlyHere}</p>
    </section>
  );
}
