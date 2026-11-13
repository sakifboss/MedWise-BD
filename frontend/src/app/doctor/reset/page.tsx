import type { Metadata } from "next";

import { BackLink } from "@/components/back-link";
import { ResetForm } from "@/components/doctor/reset-form";
import { getDict } from "@/i18n/server";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getDict();
  return { title: t.doctor.resetTitle, robots: { index: false }, referrer: "no-referrer" };
}

export default async function DoctorResetPage() {
  const t = await getDict();
  return (
    <div className="space-y-6">
      <BackLink href="/doctor">{t.doctor.title}</BackLink>
      <h1 className="text-2xl font-semibold tracking-tight">{t.doctor.resetTitle}</h1>
      <ResetForm />
    </div>
  );
}
