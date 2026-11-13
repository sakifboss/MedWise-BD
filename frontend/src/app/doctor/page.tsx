import type { Metadata } from "next";
import Link from "next/link";

import { BackLink } from "@/components/back-link";
import { DoctorHome } from "@/components/doctor/doctor-home";
import { Badge } from "@/components/ui/badge";
import { getDict } from "@/i18n/server";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getDict();
  return { title: t.doctor.title, description: t.doctor.metaDescription };
}

export default async function DoctorPage() {
  const t = await getDict();
  return (
    <div className="space-y-6">
      <BackLink href="/">{t.back.home}</BackLink>
      <header className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-2xl font-semibold tracking-tight">{t.doctor.title}</h1>
          <Badge variant="secondary">{t.doctor.pilot}</Badge>
        </div>
        <p className="text-sm text-muted-foreground">{t.doctor.intro}</p>
        <ul className="list-disc space-y-1 pl-5 text-sm">
          {t.doctor.points.map((point) => (
            <li key={point}>{point}</li>
          ))}
        </ul>
        <Link href="/doctor/privacy" className="inline-block text-sm underline underline-offset-2">
          {t.doctor.privacyLink}
        </Link>
      </header>
      <DoctorHome />
    </div>
  );
}
