import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { getDict } from "@/i18n/server";

export default async function NotFound() {
  const t = await getDict();
  return (
    <div className="space-y-4 py-10 text-center">
      <h1 className="text-xl font-semibold">{t.notFound.title}</h1>
      <p className="text-muted-foreground">{t.notFound.text}</p>
      <Link href="/" className={buttonVariants()}>
        {t.notFound.action}
      </Link>
    </div>
  );
}
