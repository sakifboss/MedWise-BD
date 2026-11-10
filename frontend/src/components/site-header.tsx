import { Camera, ClipboardList, Factory, Pill, ShieldAlert } from "lucide-react";
import Link from "next/link";

import { LanguageToggle } from "@/components/language-toggle";
import { getDict } from "@/i18n/server";

export async function SiteHeader() {
  const t = await getDict();
  const nav = [
    { href: "/prescription", label: t.nav.scan, icon: Camera },
    { href: "/interactions", label: t.nav.interactions, icon: ShieldAlert },
    { href: "/manufacturers", label: t.manufacturer.nav, icon: Factory },
    { href: "/my-medicines", label: t.myMeds.nav, icon: ClipboardList },
  ];
  return (
    <header className="sticky top-0 z-10 border-b print:static bg-background/95 backdrop-blur supports-backdrop-filter:bg-background/80">
      <div className="mx-auto flex h-14 w-full max-w-3xl items-center gap-2 px-4 sm:gap-5">
        <Link href="/" className="flex shrink-0 items-center gap-2 font-semibold tracking-tight whitespace-nowrap">
          <Pill className="size-5 text-primary" aria-hidden />
          MedWise BD
        </Link>
        <nav aria-label={t.nav.main} className="flex items-center text-sm sm:gap-4 print:hidden">
          {nav.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              aria-label={label}
              title={label}
              className="rounded-md p-1.5 text-muted-foreground transition-colors hover:text-foreground sm:p-0"
            >
              <Icon aria-hidden className="size-5 sm:hidden" />
              <span className="max-sm:hidden">{label}</span>
            </Link>
          ))}
        </nav>
        <LanguageToggle />
      </div>
    </header>
  );
}
