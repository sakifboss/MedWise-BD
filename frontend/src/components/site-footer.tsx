import Link from "next/link";

import { SaveForOffline } from "@/components/offline";
import { OsmCredit } from "@/components/pharmacy-finder";
import { InstallAppButton } from "@/components/pwa";
import { getDict } from "@/i18n/server";

export async function SiteFooter() {
  const t = await getDict();
  return (
    <footer data-site-chrome className="border-t">
      <div className="mx-auto w-full max-w-3xl space-y-1 px-4 py-6 text-xs text-muted-foreground">
        <p>{t.footer.noAdvice}</p>
        <p>{t.footer.sources}</p>
        <OsmCredit before={t.footer.mapsBefore} />
        <p>
          <Link href="/doctor" className="underline underline-offset-2">
            {t.doctor.footerLink}
          </Link>
        </p>
        <div className="flex flex-col gap-3 pt-2">
          <InstallAppButton />
          <SaveForOffline />
        </div>
      </div>
    </footer>
  );
}
