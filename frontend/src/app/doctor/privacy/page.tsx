import type { Metadata } from "next";

import { BackLink } from "@/components/back-link";
import { getDict } from "@/i18n/server";
import { DOCTOR_CONTACT_EMAIL, DOCTOR_DATA_REGION, RESTORE_WINDOW_HOURS } from "@/lib/doctor-config";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getDict();
  return { title: t.doctor.privacy.title, description: t.doctor.privacy.intro };
}

/** Public: what is stored about doctors, why, where, how long, how to delete; and the terms. */
export default async function DoctorPrivacyPage() {
  const t = await getDict();
  const p = t.doctor.privacy;
  const sections = p.sections(
    DOCTOR_DATA_REGION,
    t.doctor.restoreWindow(RESTORE_WINDOW_HOURS),
    DOCTOR_CONTACT_EMAIL || "MedWise BD",
  );
  return (
    <article className="space-y-6">
      <BackLink href="/doctor">{t.doctor.title}</BackLink>
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">{p.title}</h1>
        <p className="text-xs text-muted-foreground">{p.updated}</p>
        <p className="text-sm text-muted-foreground">{p.intro}</p>
      </header>
      {sections.map((section) => (
        <section key={section.title} className="space-y-2">
          <h2 className="text-lg font-semibold">{section.title}</h2>
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {section.items.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      ))}
    </article>
  );
}
