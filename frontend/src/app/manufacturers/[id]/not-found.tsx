import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { getDict } from "@/i18n/server";

export default async function ManufacturerNotFound() {
  const t = await getDict();
  return (
    <div className="space-y-4 py-10 text-center">
      <h1 className="text-xl font-semibold">{t.manufacturer.notFoundTitle}</h1>
      <p className="text-muted-foreground">{t.manufacturer.notFoundText}</p>
      <Link href="/manufacturers" className={buttonVariants()}>
        {t.manufacturer.all}
      </Link>
    </div>
  );
}
