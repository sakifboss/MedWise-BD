import { Pill } from "lucide-react";
import Link from "next/link";

import { SampleDataBadge } from "@/components/sample-data-badge";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-10 border-b bg-background/95 backdrop-blur supports-backdrop-filter:bg-background/80">
      <div className="mx-auto flex h-14 w-full max-w-3xl items-center justify-between gap-3 px-4">
        <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
          <Pill className="size-5 text-primary" aria-hidden />
          MedWise BD
        </Link>
        <SampleDataBadge />
      </div>
    </header>
  );
}
