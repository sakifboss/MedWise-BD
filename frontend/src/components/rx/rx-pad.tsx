"use client";

import { FilePlus2, Printer, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { StatusCard, useDoctor } from "@/components/doctor/shared";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useDict } from "@/i18n/client";
import type { DoctorProfile } from "@/lib/api";
import { MAX_LINES, newLine, type RxLine, type RxSource } from "@/lib/rx";
import { PRINT_LANGUAGES, loadPrintLanguage, savePrintLanguage } from "@/lib/rx-preferences";
import { confirmBeforeLeaving, setPrintMargins, todayIso } from "@/lib/rx-print";

import { LineEditor } from "./line-editor";
import { MedicinePicker } from "./medicine-picker";
import { RxPrint, type PrintLanguage, type RxNotes, type RxPatient } from "./rx-print";
import { RxWarnings } from "./rx-warnings";

/**
 * Patient information: kept only in this component's memory (never in localStorage, cookies or
 * any request). Every field: no autofill history, no browser spellcheck service (Chrome's enhanced
 * spellcheck sends text to Google), not offered for translation, and no voice input.
 */
const PATIENT_FIELD = { autoComplete: "off", spellCheck: false, translate: "no", "data-patient-field": "" } as const;

const TEXTAREA =
  "w-full min-w-0 rounded-lg border border-input bg-transparent px-2.5 py-1.5 text-base outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 md:text-sm dark:bg-input/30";
const SELECT =
  "h-8 rounded-lg border border-input bg-transparent px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30";

const emptyPatient = (): RxPatient => ({ name: "", age: "", sex: "", weight: "", date: todayIso() });
const EMPTY_NOTES: RxNotes = {
  complaints: "",
  findings: "",
  diagnosis: "",
  allergies: "",
  tests: "",
  advice: "",
  followUp: "",
};

function NoteField({
  id,
  label,
  value,
  onChange,
  rows = 2,
}: {
  id: keyof RxNotes;
  label: string;
  value: string;
  onChange: (value: string) => void;
  rows?: number;
}) {
  return (
    <div className="space-y-1">
      <label htmlFor={`rx-${id}`} className="text-sm font-medium">
        {label}
      </label>
      <textarea
        id={`rx-${id}`}
        rows={rows}
        maxLength={1000}
        className={TEXTAREA}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        {...PATIENT_FIELD}
      />
    </div>
  );
}

function Pad({ doctor }: { doctor: DoctorProfile }) {
  const t = useDict();
  const [patient, setPatient] = useState<RxPatient>(emptyPatient);
  const [notes, setNotes] = useState<RxNotes>(EMPTY_NOTES);
  const [lines, setLines] = useState<RxLine[]>([]);
  // The doctor's last choice on this device (a preference, never patient data); Bangla at first.
  const [language, setLanguage] = useState<PrintLanguage>(loadPrintLanguage);
  const [chamberIndex, setChamberIndex] = useState(doctor.chambers.length ? 0 : -1);
  const [confirmingNew, setConfirmingNew] = useState(false);
  const hasContent =
    lines.length > 0 ||
    Object.values(notes).some((v) => v.trim()) ||
    [patient.name, patient.age, patient.weight, patient.sex].some((v) => v.trim());
  const content = useRef(false);
  useEffect(() => {
    content.current = hasContent;
  }, [hasContent]);

  useEffect(() => confirmBeforeLeaving(() => content.current), []);
  useEffect(
    () => setPrintMargins(`${doctor.display_name} · ${t.rx.print.rx}`, t.rx.print.footer),
    [doctor.display_name, t],
  );

  const setNote = (key: keyof RxNotes) => (value: string) => setNotes((n) => ({ ...n, [key]: value }));
  const addLine = (source: RxSource) =>
    setLines((list) => (list.length >= MAX_LINES ? list : [...list, newLine(source, crypto.randomUUID())]));

  function clearAll() {
    setPatient(emptyPatient());
    setNotes(EMPTY_NOTES);
    setLines([]);
    setConfirmingNew(false);
  }

  const s = t.rx.sections;
  return (
    <>
      <div className="space-y-6 print:hidden" data-testid="rx-pad">
        <p className="flex gap-2 rounded-lg border border-emerald-300 bg-emerald-50 p-3 text-sm dark:border-emerald-800 dark:bg-emerald-950/40">
          <ShieldCheck aria-hidden className="mt-0.5 size-4 shrink-0" />
          {t.rx.privacy}
        </p>
        {doctor.status !== "verified" && <StatusCard doctor={doctor} />}

        <section className="space-y-3">
          <h2 className="text-lg font-semibold">{t.rx.patient.title}</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1 sm:col-span-2">
              <label htmlFor="rx-patient-name" className="text-sm font-medium">
                {t.rx.patient.name}
              </label>
              <Input
                id="rx-patient-name"
                value={patient.name}
                maxLength={120}
                onChange={(e) => setPatient({ ...patient, name: e.target.value })}
                {...PATIENT_FIELD}
              />
            </div>
            <div className="space-y-1">
              <label htmlFor="rx-patient-age" className="text-sm font-medium">
                {t.rx.patient.age}
              </label>
              <Input
                id="rx-patient-age"
                value={patient.age}
                maxLength={20}
                onChange={(e) => setPatient({ ...patient, age: e.target.value })}
                {...PATIENT_FIELD}
              />
            </div>
            <div className="space-y-1">
              <label htmlFor="rx-patient-sex" className="block text-sm font-medium">
                {t.rx.patient.sex}
              </label>
              <select
                id="rx-patient-sex"
                className={SELECT}
                value={patient.sex}
                onChange={(e) => setPatient({ ...patient, sex: e.target.value as RxPatient["sex"] })}
                {...PATIENT_FIELD}
              >
                {(Object.keys(t.rx.patient.sexes) as RxPatient["sex"][]).map((k) => (
                  <option key={k} value={k}>
                    {t.rx.patient.sexes[k]}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <label htmlFor="rx-patient-weight" className="text-sm font-medium">
                {t.rx.patient.weight}
              </label>
              <Input
                id="rx-patient-weight"
                value={patient.weight}
                maxLength={20}
                onChange={(e) => setPatient({ ...patient, weight: e.target.value })}
                {...PATIENT_FIELD}
              />
            </div>
            <div className="space-y-1">
              <label htmlFor="rx-patient-date" className="text-sm font-medium">
                {t.rx.patient.date}
              </label>
              <Input
                id="rx-patient-date"
                type="date"
                value={patient.date}
                onChange={(e) => setPatient({ ...patient, date: e.target.value })}
                {...PATIENT_FIELD}
              />
            </div>
          </div>
        </section>

        <section className="grid gap-3 sm:grid-cols-2">
          <NoteField id="complaints" label={s.complaints} value={notes.complaints} onChange={setNote("complaints")} rows={3} />
          <NoteField id="findings" label={s.findings} value={notes.findings} onChange={setNote("findings")} rows={3} />
          <NoteField id="diagnosis" label={s.diagnosis} value={notes.diagnosis} onChange={setNote("diagnosis")} />
          <NoteField id="allergies" label={s.allergies} value={notes.allergies} onChange={setNote("allergies")} />
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold">{s.medicines}</h2>
          {lines.length > 0 && (
            <ol className="space-y-3">
              {lines.map((line, i) => (
                <LineEditor
                  key={line.id}
                  line={line}
                  index={i}
                  onChange={(next) => setLines((list) => list.map((l) => (l.id === line.id ? next : l)))}
                  onRemove={() => setLines((list) => list.filter((l) => l.id !== line.id))}
                />
              ))}
            </ol>
          )}
          <MedicinePicker disabled={lines.length >= MAX_LINES} onPick={addLine} />
          <RxWarnings lines={lines} />
        </section>

        <section className="grid gap-3 sm:grid-cols-2">
          <NoteField id="tests" label={s.tests} value={notes.tests} onChange={setNote("tests")} rows={3} />
          <NoteField id="advice" label={s.advice} value={notes.advice} onChange={setNote("advice")} rows={3} />
          <div className="space-y-1">
            <label htmlFor="rx-followUp" className="text-sm font-medium">
              {s.followUp}
            </label>
            <Input
              id="rx-followUp"
              type="date"
              value={notes.followUp}
              onChange={(e) => setNote("followUp")(e.target.value)}
              {...PATIENT_FIELD}
            />
          </div>
        </section>

        <section className="flex flex-wrap items-end gap-3 border-t pt-4">
          <div className="space-y-1">
            <label htmlFor="rx-print-language" className="block text-sm font-medium">
              {t.rx.print.language}
            </label>
            <select
              id="rx-print-language"
              className={SELECT}
              value={language}
              onChange={(e) => {
                const next = e.target.value as PrintLanguage;
                setLanguage(next);
                savePrintLanguage(next);
              }}
            >
              {PRINT_LANGUAGES.map((k) => (
                <option key={k} value={k}>
                  {t.rx.print.langs[k]}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <label htmlFor="rx-print-chamber" className="block text-sm font-medium">
              {t.rx.print.chamber}
            </label>
            <select
              id="rx-print-chamber"
              className={SELECT}
              value={chamberIndex}
              onChange={(e) => setChamberIndex(Number(e.target.value))}
            >
              <option value={-1}>{t.rx.print.noChamber}</option>
              {doctor.chambers.map((c, i) => (
                <option key={`${c.name}-${i}`} value={i}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
          <Button onClick={() => window.print()}>
            <Printer aria-hidden />
            {t.rx.print.button}
          </Button>
          {confirmingNew ? (
            <span className="flex flex-wrap items-center gap-2 text-sm">
              {t.rx.newConfirm}
              <Button variant="destructive" size="sm" onClick={clearAll}>
                {t.rx.newConfirmYes}
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setConfirmingNew(false)}>
                {t.rx.cancel}
              </Button>
            </span>
          ) : (
            <Button variant="outline" onClick={() => setConfirmingNew(true)}>
              <FilePlus2 aria-hidden />
              {t.rx.newRx}
            </Button>
          )}
        </section>
      </div>

      <RxPrint
        doctor={doctor}
        chamberIndex={chamberIndex}
        patient={patient}
        notes={notes}
        lines={lines}
        language={language}
      />
    </>
  );
}

export function RxPad() {
  const t = useDict();
  const { state } = useDoctor();
  if (state.kind === "loading") return <Skeleton className="h-80 w-full" />;
  if (state.kind === "out") {
    return (
      <p className="text-sm">
        {t.doctor.needLogin}{" "}
        <Link href="/doctor" className="underline underline-offset-2">
          {t.doctor.tabs.login}
        </Link>
      </p>
    );
  }
  if (state.doctor.status === "rejected" && !state.doctor.is_demo) {
    return (
      <div className="space-y-3">
        <p className="text-sm">{t.rx.notAllowed}</p>
        <StatusCard doctor={state.doctor} />
      </div>
    );
  }
  return <Pad doctor={state.doctor} />;
}
