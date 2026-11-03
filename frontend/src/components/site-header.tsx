import { Camera, Pill, ShieldAlert } from "lucide-react";
import Link from "next/link";

const NAV = [
  { href: "/prescription", label: "Scan", icon: Camera },
  { href: "/interactions", label: "Interactions", icon: ShieldAlert },
];

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-10 border-b bg-background/95 backdrop-blur supports-backdrop-filter:bg-background/80">
      <div className="mx-auto flex h-14 w-full max-w-3xl items-center gap-2 px-4 sm:gap-5">
        <Link href="/" className="flex shrink-0 items-center gap-2 font-semibold tracking-tight whitespace-nowrap">
          <Pill className="size-5 text-primary" aria-hidden />
          MedWise BD
        </Link>
        <nav aria-label="Main" className="flex items-center text-sm sm:gap-4">
          {NAV.map(({ href, label, icon: Icon }) => (
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
      </div>
    </header>
  );
}
