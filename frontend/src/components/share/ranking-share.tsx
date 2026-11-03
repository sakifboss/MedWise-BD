"use client";

import { usePathname, useSearchParams } from "next/navigation";

import { QUANTITY_PARAM, useSavings } from "@/components/savings/savings-context";
import { ShareActions } from "@/components/share/share-actions";

/** Share buttons for a ranking page; the link carries the calculator's quantity (?per=). */
export function RankingShare({ title, text }: { title: string; text: string }) {
  const { quantity } = useSavings();
  const pathname = usePathname();
  const params = new URLSearchParams(useSearchParams());
  if (quantity === null) params.delete(QUANTITY_PARAM);
  else params.set(QUANTITY_PARAM, String(quantity));
  const query = params.toString();
  return <ShareActions title={title} text={text} url={query ? `${pathname}?${query}` : pathname} />;
}
