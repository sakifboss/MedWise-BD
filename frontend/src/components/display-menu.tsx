"use client";

import { Check, Monitor, Moon, Sun } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useSyncExternalStore, useTransition } from "react";

import { useDict } from "@/i18n/client";
import {
  applyTheme,
  pageTheme,
  subscribeTheme,
  syncThemeWithCookie,
  THEMES,
  type Theme,
} from "@/lib/theme";
import { cn } from "@/lib/utils";

const ICONS = { system: Monitor, light: Sun, dark: Moon } as const;
const MENU_ID = "display-menu";

/**
 * Header "Display" menu (a native popover: no extra script, closes on outside tap or Escape).
 * The choice is applied at once on the page and saved in a cookie for the server.
 */
export function DisplayMenu({ initial }: { initial: Theme }) {
  const t = useDict();
  const d = t.display;
  const router = useRouter();
  const [, startTransition] = useTransition();
  const theme = useSyncExternalStore(subscribeTheme, pageTheme, () => initial);

  useEffect(syncThemeWithCookie, []);

  function choose(next: Theme) {
    applyTheme(next);
    document.getElementById(MENU_ID)?.hidePopover?.();
    // Re-render server parts too (the address-bar colour); page state is kept.
    startTransition(() => router.refresh());
  }

  const Icon = ICONS[theme];
  return (
    <div className="print:hidden">
      <button
        type="button"
        popoverTarget={MENU_ID}
        aria-label={d.label(d.themes[theme])}
        title={d.label(d.themes[theme])}
        className="inline-flex size-8 items-center justify-center rounded-md border text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        data-testid="display-button"
      >
        <Icon aria-hidden className="size-4" />
      </button>
      <div
        id={MENU_ID}
        popover="auto"
        aria-label={d.menu}
        className="fixed inset-auto top-14 right-4 m-0 w-52 rounded-lg border bg-popover p-2 text-popover-foreground shadow-lg"
        data-testid="display-menu"
      >
        <p className="px-2 pt-1 pb-1.5 text-xs font-medium text-muted-foreground" id="theme-heading">
          {d.theme}
        </p>
        <div role="radiogroup" aria-labelledby="theme-heading" className="grid gap-0.5">
          {THEMES.map((option) => {
            const OptionIcon = ICONS[option];
            const selected = option === theme;
            return (
              <button
                key={option}
                type="button"
                role="radio"
                aria-checked={selected}
                onClick={() => choose(option)}
                className={cn(
                  "flex items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted",
                  selected && "font-medium",
                )}
              >
                <OptionIcon aria-hidden className="size-4" />
                <span className="flex-1">{d.themes[option]}</span>
                {selected && <Check aria-hidden className="size-4 text-primary" />}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
