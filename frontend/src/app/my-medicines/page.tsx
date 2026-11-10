import type { Metadata } from "next";

import { BackLink } from "@/components/back-link";
import { MyMedicinesView } from "@/components/my-medicines/my-medicines-view";
import { getDict } from "@/i18n/server";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getDict();
  // The list lives only on the device, so there is nothing here for search engines.
  return { title: t.myMeds.title, description: t.myMeds.privacy, robots: { index: false } };
}

export default async function MyMedicinesPage() {
  const t = await getDict();
  return (
    <div className="space-y-6">
      <BackLink href="/">{t.back.home}</BackLink>
      <MyMedicinesView />
    </div>
  );
}
