import type { Metadata } from "next";

import { BackLink } from "@/components/back-link";
import { AccountPanel } from "@/components/doctor/account-panel";
import { getDict } from "@/i18n/server";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getDict();
  return { title: t.doctor.accountTitle, robots: { index: false } };
}

export default async function DoctorAccountPage() {
  const t = await getDict();
  return (
    <div className="space-y-6">
      <BackLink href="/doctor">{t.doctor.title}</BackLink>
      <h1 className="text-2xl font-semibold tracking-tight">{t.doctor.accountTitle}</h1>
      <AccountPanel />
    </div>
  );
}
