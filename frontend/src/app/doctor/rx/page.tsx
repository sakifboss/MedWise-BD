import type { Metadata } from "next";

import { BackLink } from "@/components/back-link";
import { RxPad } from "@/components/rx/rx-pad";
import { getDict } from "@/i18n/server";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getDict();
  return { title: t.rx.title, robots: { index: false } };
}

export default async function RxPadPage() {
  const t = await getDict();
  return (
    <div className="space-y-6">
      <div className="print:hidden">
        <BackLink href="/doctor">{t.doctor.title}</BackLink>
      </div>
      <h1 className="text-2xl font-semibold tracking-tight print:hidden">{t.rx.title}</h1>
      <RxPad />
    </div>
  );
}
