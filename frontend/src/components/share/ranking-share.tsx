"use client";

import { usePathname, useSearchParams } from "next/navigation";

import { QUANTITY_PARAM, useSavings } from "@/components/savings/savings-context";
import { ShareActions } from "@/components/share/share-actions";

/**
 * Share buttons for a ranking page; the link carries the calculator's quantity (?per=).
 * `path` is the stable page address (a brand's code URL) when the page knows it, so a page opened
 * from an old id link still shares the code link.
 */
export function RankingShare({ title, text, path }: { title: string; text: string; path?: string }) {
  const { quantity } = useSavings();
  const current = usePathname();
  const pathname = path ?? current;
  const params = new URLSearchParams(useSearchParams());
  if (quantity === null) params.delete(QUANTITY_PARAM);
  else params.set(QUANTITY_PARAM, String(quantity));
  const query = params.toString();
  return <ShareActions title={title} text={text} url={query ? `${pathname}?${query}` : pathname} />;
}
