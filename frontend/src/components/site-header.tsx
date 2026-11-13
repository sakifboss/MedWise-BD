import { BriefcaseMedical, Camera, ClipboardList, Factory, Pill, ShieldAlert, Stethoscope } from "lucide-react";
import Link from "next/link";

import { DisplayMenu } from "@/components/display-menu";
import { LanguageToggle } from "@/components/language-toggle";
import type { Dict } from "@/i18n/dictionaries";
import { getDict, getTextSize, getTheme } from "@/i18n/server";

/** The site's sections, in one place for the header (wide screens) and the phone menu. */
export function navItems(t: Dict) {
  return [
    { href: "/prescription", label: t.nav.scan, title: t.nav.scan, icon: Camera },
    { href: "/interactions", label: t.nav.interactions, title: t.nav.interactions, icon: ShieldAlert },
    { href: "/manufacturers", label: t.manufacturer.nav, title: t.manufacturer.nav, icon: Factory },
    { href: "/my-medicines", label: t.myMeds.nav, title: t.myMeds.nav, icon: ClipboardList },
    { href: "/symptoms", label: t.symptoms.nav, title: t.symptoms.nav, icon: Stethoscope },
    { href: "/doctor", label: t.doctor.nav, title: t.doctor.footerLink, icon: BriefcaseMedical },
  ];
}

export async function SiteHeader() {
  const [t, theme, textSize] = await Promise.all([getDict(), getTheme(), getTextSize()]);
  return (
    <header data-site-chrome className="sticky top-0 z-10 border-b print:static bg-background/95 backdrop-blur supports-backdrop-filter:bg-background/80">
      <div className="mx-auto flex h-14 w-full max-w-3xl items-center gap-2 px-4 md:gap-4 lg:max-w-5xl">
        <Link href="/" className="-ml-1 flex min-h-11 shrink-0 items-center gap-2 rounded-md px-1 font-semibold tracking-tight whitespace-nowrap">
          <Pill className="size-5 text-primary" aria-hidden />
          {/* Between md and lg the six section names need the room; the icon still links home. */}
          <span className="max-[330px]:sr-only md:max-lg:sr-only in-data-[text=large]:md:max-lg:not-sr-only">MedWise BD</span>
        </Link>
        {/* Wide screens: the sections by name (from lg with Large text). Otherwise the menu below. */}
        <nav aria-label={t.nav.main} className="flex items-center gap-4 text-sm max-md:hidden in-data-[text=large]:max-lg:hidden print:hidden lg:gap-5">
          {navItems(t).map(({ href, label, title }) => (
            <Link
              key={href}
              href={href}
              title={title}
              className="py-2 whitespace-nowrap text-muted-foreground transition-colors hover:text-foreground"
            >
              {label}
            </Link>
          ))}
        </nav>
        <div className="ml-auto flex shrink-0 items-center gap-1.5">
          <DisplayMenu initial={theme} initialTextSize={textSize} />
          <LanguageToggle />
        </div>
      </div>
    </header>
  );
}

/**
 * Phones (below md; below lg with Large text): every section as a large button with its name,
 * under the header. It scrolls away with the page, so only the slim top bar stays on screen.
 */
export async function MobileNav() {
  const t = await getDict();
  return (
    <nav
      data-site-chrome
      aria-label={t.nav.main}
      className="border-b md:hidden in-data-[text=large]:md:max-lg:block print:hidden"
    >
      <ul className="mx-auto grid w-full max-w-3xl grid-cols-3 gap-1.5 px-3 py-2 sm:grid-cols-6">
        {navItems(t).map(({ href, label, title, icon: Icon }) => (
          <li key={href}>
            <Link
              href={href}
              title={title}
              className="flex min-h-14 flex-col items-center justify-center gap-1 rounded-lg px-1 py-1.5 text-center text-xs leading-tight text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              <Icon aria-hidden className="size-5 text-primary" />
              <span>{label}</span>
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
