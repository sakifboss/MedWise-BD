"use client";

import { Languages } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTransition } from "react";

import { useDict } from "@/i18n/client";
import { LANG_COOKIE } from "@/i18n/dictionaries";

const ONE_YEAR = 60 * 60 * 24 * 365;

export function LanguageToggle() {
  const t = useDict();
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const next = t.lang === "en" ? "bn" : "en";

  function switchLanguage() {
    document.cookie = `${LANG_COOKIE}=${next}; path=/; max-age=${ONE_YEAR}; samesite=lax`;
    // Server components re-render with the new cookie; client state (e.g. a scanned prescription) is kept.
    startTransition(() => router.refresh());
  }

  return (
    <button
      type="button"
      onClick={switchLanguage}
      disabled={pending}
      aria-label={t.nav.switchLabel}
      title={t.nav.switchLabel}
      lang={next}
      className="ml-auto inline-flex print:hidden items-center gap-1.5 rounded-md border px-2.5 py-1 text-sm font-medium transition-colors hover:bg-muted disabled:opacity-60"
    >
      <Languages aria-hidden className="size-4" />
      {t.nav.switchTo}
    </button>
  );
}
