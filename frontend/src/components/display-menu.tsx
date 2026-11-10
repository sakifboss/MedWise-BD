"use client";

import { ALargeSmall, Check, Monitor, Moon, Sun, Type, type LucideIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useSyncExternalStore, useTransition } from "react";

import { useDict } from "@/i18n/client";
import {
  applyTextSize,
  pageTextSize,
  subscribeTextSize,
  syncTextSizeWithCookie,
  TEXT_SIZES,
  type TextSize,
} from "@/lib/text-size";
import { applyTheme, pageTheme, subscribeTheme, syncThemeWithCookie, THEMES, type Theme } from "@/lib/theme";
import { cn } from "@/lib/utils";

const THEME_ICONS: Record<Theme, LucideIcon> = { system: Monitor, light: Sun, dark: Moon };
const SIZE_ICONS: Record<TextSize, LucideIcon> = { normal: Type, large: ALargeSmall };
const MENU_ID = "display-menu";

function Choices<T extends string>({
  id,
  heading,
  options,
  labels,
  icons,
  value,
  onChoose,
}: {
  id: string;
  heading: string;
  options: readonly T[];
  labels: Record<T, string>;
  icons: Record<T, LucideIcon>;
  value: T;
  onChoose: (value: T) => void;
}) {
  return (
    <>
      <p className="px-2 pt-1 pb-1.5 text-xs font-medium text-muted-foreground" id={id}>
        {heading}
      </p>
      <div role="radiogroup" aria-labelledby={id} className="grid gap-0.5">
        {options.map((option) => {
          const Icon: LucideIcon = icons[option];
          const selected = option === value;
          return (
            <button
              key={option}
              type="button"
              role="radio"
              aria-checked={selected}
              onClick={() => onChoose(option)}
              className={cn(
                "flex items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted",
                selected && "font-medium",
              )}
            >
              <Icon aria-hidden className="size-4" />
              <span className="flex-1">{labels[option]}</span>
              {selected && <Check aria-hidden className="size-4 text-primary" />}
            </button>
          );
        })}
      </div>
    </>
  );
}

/**
 * Header "Display" menu (a native popover: no extra script, closes on outside tap or Escape):
 * theme and text size. A choice is applied at once on the page and saved in a cookie for the server.
 */
export function DisplayMenu({ initial, initialTextSize }: { initial: Theme; initialTextSize: TextSize }) {
  const t = useDict();
  const d = t.display;
  const router = useRouter();
  const [, startTransition] = useTransition();
  const theme = useSyncExternalStore(subscribeTheme, pageTheme, () => initial);
  const textSize = useSyncExternalStore(subscribeTextSize, pageTextSize, () => initialTextSize);

  useEffect(() => {
    syncThemeWithCookie();
    syncTextSizeWithCookie();
  }, []);

  function done() {
    document.getElementById(MENU_ID)?.hidePopover?.();
    // Re-render server parts too (the address-bar colour); page state is kept.
    startTransition(() => router.refresh());
  }

  const Icon = THEME_ICONS[theme];
  const label = d.label(d.themes[theme], d.textSizeWords[textSize]);
  return (
    <div className="print:hidden">
      <button
        type="button"
        popoverTarget={MENU_ID}
        aria-label={label}
        title={label}
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
        <Choices
          id="theme-heading"
          heading={d.theme}
          options={THEMES}
          labels={d.themes}
          icons={THEME_ICONS}
          value={theme}
          onChoose={(next) => {
            applyTheme(next);
            done();
          }}
        />
        <div className="my-2 border-t" />
        <Choices
          id="text-size-heading"
          heading={d.textSize}
          options={TEXT_SIZES}
          labels={d.textSizes}
          icons={SIZE_ICONS}
          value={textSize}
          onChoose={(next) => {
            applyTextSize(next);
            done();
          }}
        />
      </div>
    </div>
  );
}
