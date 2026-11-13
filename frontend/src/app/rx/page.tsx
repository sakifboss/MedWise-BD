import type { Metadata } from "next";

import { RxPatientView } from "@/components/rx/rx-patient-view";
import { getDict } from "@/i18n/server";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getDict();
  return {
    title: t.rxPage.title,
    description: t.rxPage.metaDescription,
    robots: { index: false },
    referrer: "no-referrer",
  };
}

/** Public page for a prescription's QR code. The prescription is in the URL after "#": it is read
 * on the device and never reaches any server. */
export default async function RxPage() {
  const t = await getDict();
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">{t.rxPage.title}</h1>
      <RxPatientView />
    </div>
  );
}
