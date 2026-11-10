import { Camera, ClipboardList, Factory, Pill, ShieldAlert, Stethoscope } from "lucide-react";
import Link from "next/link";

import { DisplayMenu } from "@/components/display-menu";
import { LanguageToggle } from "@/components/language-toggle";
import { getDict, getTheme } from "@/i18n/server";

export async function SiteHeader() {
  const [t, theme] = await Promise.all([getDict(), getTheme()]);
  const nav = [
    { href: "/prescription", label: t.nav.scan, icon: Camera },
    { href: "/interactions", label: t.nav.interactions, icon: ShieldAlert },
    { href: "/manufacturers", label: t.manufacturer.nav, icon: Factory },
    { href: "/my-medicines", label: t.myMeds.nav, icon: ClipboardList },
    { href: "/symptoms", label: t.symptoms.nav, icon: Stethoscope },
  ];
  return (
    <header className="sticky top-0 z-10 border-b print:static bg-background/95 backdrop-blur supports-backdrop-filter:bg-background/80">
      <div className="mx-auto flex h-14 w-full max-w-3xl items-center gap-2 px-4 max-[360px]:gap-1 max-[360px]:px-3 md:gap-5">
        <Link href="/" className="flex shrink-0 items-center gap-2 font-semibold tracking-tight whitespace-nowrap">
          <Pill className="size-5 text-primary" aria-hidden />
          {/* Five nav icons and the language button need the room on small phones. */}
          <span className="max-[460px]:sr-only">MedWise BD</span>
        </Link>
        <nav aria-label={t.nav.main} className="flex items-center text-sm md:gap-4 print:hidden">
          {nav.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              aria-label={label}
              title={label}
              className="rounded-md p-1.5 text-muted-foreground transition-colors hover:text-foreground max-[360px]:p-1 md:p-0"
            >
              <Icon aria-hidden className="size-5 md:hidden" />
              <span className="max-md:hidden">{label}</span>
            </Link>
          ))}
        </nav>
        <div className="ml-auto flex shrink-0 items-center gap-1.5 max-[360px]:gap-1">
          <DisplayMenu initial={theme} />
          <LanguageToggle />
        </div>
      </div>
    </header>
  );
}
