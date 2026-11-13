"use client";

import { useDict } from "@/i18n/client";
import type { DoctorProfile } from "@/lib/api";
import { instruction, type RxLine } from "@/lib/rx";
import type { PrintLanguage } from "@/lib/rx-preferences";

import { lineTitle } from "./line-editor";

export type { PrintLanguage };

export type RxPatient = {
  name: string;
  age: string;
  sex: "" | "female" | "male" | "other";
  weight: string;
  date: string;
};

export type RxNotes = {
  complaints: string;
  findings: string;
  diagnosis: string;
  allergies: string;
  tests: string;
  advice: string;
  followUp: string;
};

function Block({ title, text }: { title: string; text: string }) {
  if (!text.trim()) return null;
  return (
    <div className="mb-3 break-inside-avoid">
      <p className="text-[9pt] font-semibold tracking-wide uppercase">{title}</p>
      <p className="whitespace-pre-wrap">{text}</p>
    </div>
  );
}

/**
 * The A4 prescription (print only; hidden on screen). The browser's print gives the PDF and shapes
 * Bangla correctly. The doctor's name on page 2 onwards, the footer and page numbers are in the
 * @page margins (globals.css); the DEMO or not-verified mark repeats on every page (fixed).
 */
export function RxPrint({
  doctor,
  chamberIndex,
  patient,
  notes,
  lines,
  language,
}: {
  doctor: DoctorProfile;
  chamberIndex: number;
  patient: RxPatient;
  notes: RxNotes;
  lines: RxLine[];
  language: PrintLanguage;
}) {
  const t = useDict();
  const p = t.rx.print;
  const chamber = chamberIndex >= 0 ? doctor.chambers[chamberIndex] : undefined;
  const mark = doctor.is_demo ? p.demo : doctor.status !== "verified" ? p.notVerified : null;
  const date = patient.date ? t.fmt.date(new Date(`${patient.date}T00:00:00`)) : "";
  const followUp = notes.followUp ? t.fmt.date(new Date(`${notes.followUp}T00:00:00`)) : "";
  const sex = patient.sex ? t.rx.patient.sexes[patient.sex] : "";

  return (
    <div data-rx-print className="rx-print hidden bg-white text-[10.5pt] leading-snug text-black print:block" translate="no">
      {mark && (
        <div aria-hidden className="rx-mark">
          {mark}
        </div>
      )}
      {mark && <p className="mb-2 border border-black px-2 py-1 text-center text-[10pt] font-semibold">{mark}</p>}

      <header className="flex justify-between gap-4 border-b-2 border-black pb-2">
        <div>
          <p className="text-[15pt] font-bold">{doctor.display_name}</p>
          {doctor.display_name_bn && <p className="text-[12pt] font-semibold">{doctor.display_name_bn}</p>}
          <p>{doctor.degrees}</p>
          <p>{doctor.specialty}</p>
          <p>
            {p.bmdc}: {doctor.bmdc_number}
          </p>
        </div>
        <div className="max-w-[45%] text-right text-[9.5pt]">
          {chamber && (
            <>
              <p className="font-semibold">{chamber.name}</p>
              <p>{chamber.address}</p>
              <p>{chamber.hours}</p>
              {chamber.phone && <p>{chamber.phone}</p>}
            </>
          )}
          {doctor.phone && <p>{doctor.phone}</p>}
        </div>
      </header>

      <p className="flex flex-wrap gap-x-6 border-b border-black py-1.5" data-testid="rx-print-patient">
        <span>
          {t.rx.patient.name}: <strong>{patient.name}</strong>
        </span>
        {patient.age && (
          <span>
            {p.age}: {patient.age}
          </span>
        )}
        {sex && (
          <span>
            {p.sex}: {sex}
          </span>
        )}
        {patient.weight && (
          <span>
            {p.weight}: {patient.weight}
          </span>
        )}
        {date && (
          <span>
            {p.date}: {date}
          </span>
        )}
      </p>

      <div className="grid grid-cols-[32%_1fr] gap-4 pt-3">
        <aside className="border-r border-black pr-3">
          <Block title={t.rx.sections.complaints} text={notes.complaints} />
          <Block title={t.rx.sections.findings} text={notes.findings} />
          <Block title={t.rx.sections.diagnosis} text={notes.diagnosis} />
          <Block title={t.rx.sections.allergies} text={notes.allergies} />
          <Block title={t.rx.sections.tests} text={notes.tests} />
        </aside>
        <section>
          <p className="text-[18pt] leading-none font-bold italic">{p.rx}</p>
          <ol className="mt-2 space-y-2.5">
            {lines.map((line, i) => {
              const title = lineTitle(line);
              const bn = instruction(line, "bn");
              const en = instruction(line, "en");
              return (
                <li key={line.id} className="break-inside-avoid">
                  <p className="font-semibold">
                    {i + 1}. {title.name}
                    {title.detail && <span className="font-normal"> ({title.detail})</span>}
                  </p>
                  {line.pattern && <p className="pl-4">{line.pattern}</p>}
                  {(language === "both" || language === "bn") && bn && (
                    <p className="pl-4" lang="bn">
                      {bn}
                    </p>
                  )}
                  {(language === "both" || language === "en") && en && (
                    <p className="pl-4" lang="en">
                      {en}
                    </p>
                  )}
                  {line.note && <p className="pl-4 italic">{line.note}</p>}
                  {line.source.kind !== "free" && (
                    <p className="pl-4 text-[9pt]">{line.substitution ? p.substitutionAllowed : p.brandOnly}</p>
                  )}
                </li>
              );
            })}
          </ol>
          <div className="mt-4">
            <Block title={t.rx.sections.advice} text={notes.advice} />
            {followUp && (
              <p className="break-inside-avoid">
                <strong>{p.followUp}:</strong> {followUp}
              </p>
            )}
          </div>
        </section>
      </div>

      <div className="mt-12 flex justify-end break-inside-avoid">
        <p className="w-56 border-t border-black pt-1 text-center">{p.signature}</p>
      </div>
    </div>
  );
}
