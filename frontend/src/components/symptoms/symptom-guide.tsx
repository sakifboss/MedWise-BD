"use client";

import { ArrowLeft, Loader2, Phone, RotateCcw, Siren, Stethoscope } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { useMyMedicines } from "@/components/my-medicines/use-my-medicines";
import { ShareActions } from "@/components/share/share-actions";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useDict } from "@/i18n/client";
import { api, isRateLimited } from "@/lib/api";
import {
  TEXT_MAX,
  groupFlags,
  lines,
  noteText,
  readyAnswers,
  type SymptomAnswers,
  type SymptomResult,
  type SymptomSetup,
} from "@/lib/symptom-guide";
import { cn } from "@/lib/utils";

type Step = "checklist" | "emergency" | "form" | "result";
type Form = {
  text: string;
  since: SymptomAnswers["since"] | null;
  severity: SymptomAnswers["severity"] | null;
  age_group: SymptomAnswers["age_group"] | null;
  pregnant: SymptomAnswers["pregnant"] | null;
};
const EMPTY: Form = { text: "", since: null, severity: null, age_group: null, pregnant: null };

/** Full screen: call 999. The only way on is back to the checklist (to untick a mistake). */
function EmergencyScreen({ fromAi, onBack }: { fromAi: boolean; onBack: () => void }) {
  const s = useDict().symptoms;
  const call = useRef<HTMLAnchorElement>(null);
  useEffect(() => call.current?.focus(), []);
  return (
    <div
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="emergency-title"
      aria-describedby="emergency-text"
      data-testid="emergency-screen"
      className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-6 overflow-y-auto bg-red-700 p-6 text-center text-white"
    >
      <Siren aria-hidden className="size-14" />
      <h2 id="emergency-title" className="text-2xl font-bold">
        {s.emergencyTitle}
      </h2>
      {fromAi && <p className="max-w-md text-lg">{s.emergencyAi}</p>}
      <p id="emergency-text" className="max-w-md text-xl font-semibold">
        {s.emergency}
      </p>
      <a
        ref={call}
        href="tel:999"
        className="inline-flex items-center gap-3 rounded-full bg-white px-8 py-4 text-2xl font-bold text-red-700 shadow-lg focus-visible:outline-4 focus-visible:outline-offset-4 focus-visible:outline-white"
      >
        <Phone aria-hidden className="size-7" />
        {s.call999}
      </a>
      <button type="button" onClick={onBack} className="inline-flex items-center gap-1 text-sm underline underline-offset-4">
        <ArrowLeft aria-hidden className="size-4" />
        {s.backToChecklist}
      </button>
    </div>
  );
}

function Choice<T extends string>({
  legend,
  name,
  options,
  value,
  onChange,
}: {
  legend: string;
  name: string;
  options: Record<T, string>;
  value: T | null;
  onChange: (value: T) => void;
}) {
  return (
    <fieldset className="space-y-2">
      <legend className="text-sm font-medium">{legend}</legend>
      <div className="flex flex-wrap gap-2">
        {(Object.entries(options) as [T, string][]).map(([key, label]) => (
          <label
            key={key}
            className="cursor-pointer rounded-lg border px-3 py-1.5 text-sm has-checked:border-primary has-checked:bg-primary/10 has-focus-visible:ring-2 has-focus-visible:ring-ring"
          >
            <input
              type="radio"
              name={name}
              value={key}
              checked={value === key}
              onChange={() => onChange(key)}
              className="sr-only"
            />
            {label}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

export function SymptomGuide({ setup }: { setup: SymptomSetup }) {
  const t = useDict();
  const s = t.symptoms;
  const [step, setStep] = useState<Step>("checklist");
  const [ticked, setTicked] = useState<Set<string>>(new Set());
  const [fromAi, setFromAi] = useState(false);
  const [form, setForm] = useState<Form>(EMPTY);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ answers: SymptomAnswers; data: SymptomResult } | null>(null);
  const [note, setNote] = useState({ main: "", duration: "", others: "" });
  const [includeMeds, setIncludeMeds] = useState(false);
  const { list } = useMyMedicines();
  const top = useRef<HTMLDivElement>(null);

  const groups = groupFlags(setup.red_flags);
  const answers = readyAnswers({ ...form, lang: t.lang });
  const general = setup.specialties.find((sp) => sp.id === "general_medicine");

  function go(next: Step) {
    setStep(next);
    top.current?.scrollIntoView({ block: "start" });
  }

  function toggle(id: string) {
    const next = new Set(ticked);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setTicked(next);
    if (next.size > 0) {
      setFromAi(false);
      setStep("emergency"); // the flow stops here
    }
  }

  async function submit() {
    if (!answers) return;
    setSending(true);
    setError(null);
    try {
      const data = await api.symptomGuide(answers);
      if (data.emergency) {
        setFromAi(true);
        setStep("emergency");
        return;
      }
      setResult({ answers, data });
      setNote({
        main: data.note?.main_problem ?? "",
        duration: data.note?.duration ?? "",
        others: (data.note?.other_symptoms ?? []).join("\n"),
      });
      setIncludeMeds(false);
      go("result");
    } catch (e) {
      setError(isRateLimited(e) ? s.busy : s.failed);
    } finally {
      setSending(false);
    }
  }

  function restart() {
    setTicked(new Set());
    setForm(EMPTY);
    setResult(null);
    setError(null);
    go("checklist");
  }

  const shared =
    result &&
    noteText(
      { main_problem: note.main, duration: note.duration, other_symptoms: lines(note.others) },
      result.answers,
      includeMeds ? list.items : [],
      s.noteLabels,
    );

  return (
    <div ref={top} className="scroll-mt-20 space-y-6">
      <Alert data-testid="guide-intro">
        <Stethoscope aria-hidden />
        <AlertDescription className="font-medium text-foreground">{s.intro}</AlertDescription>
      </Alert>

      {step === "emergency" && (
        <EmergencyScreen
          fromAi={fromAi}
          onBack={() => {
            setTicked(new Set());
            setFromAi(false);
            go("checklist");
          }}
        />
      )}

      {step === "checklist" && (
        <section className="space-y-4" aria-labelledby="step1">
          <div className="space-y-1">
            <h2 id="step1" className="text-lg font-semibold">
              {s.step1Title}
            </h2>
            <p className="text-sm text-muted-foreground">{s.step1Text}</p>
          </div>
          {groups.map((g) => (
            <Card key={g.group} data-testid="red-flag-group">
              <CardContent className="space-y-2">
                <h3 className="font-medium">{s.groups[g.group] ?? g.group}</h3>
                <ul className="space-y-2">
                  {g.items.map((item) => (
                    <li key={item.id}>
                      <label className="flex cursor-pointer items-start gap-3 text-sm">
                        <input
                          type="checkbox"
                          className="mt-0.5 size-5 shrink-0 accent-red-700"
                          checked={ticked.has(item.id)}
                          onChange={() => toggle(item.id)}
                          data-testid="red-flag"
                        />
                        <span>{item.text}</span>
                      </label>
                    </li>
                  ))}
                </ul>
                <p className="text-xs text-muted-foreground">
                  {g.sources.map((url, i) => (
                    <a key={url} href={url} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2">
                      {s.source}
                      {g.sources.length > 1 ? ` ${i + 1}` : ""}
                      {i < g.sources.length - 1 ? " · " : ""}
                    </a>
                  ))}
                </p>
              </CardContent>
            </Card>
          ))}
          <Button size="lg" className="w-full" onClick={() => go("form")}>
            {s.noneOfThese}
          </Button>
        </section>
      )}

      {step === "form" && (
        <section className="space-y-5" aria-labelledby="step2">
          <h2 id="step2" className="text-lg font-semibold">
            {s.step2Title}
          </h2>
          <label className="grid gap-1.5">
            <span className="text-sm font-medium">{s.describe}</span>
            <textarea
              value={form.text}
              maxLength={TEXT_MAX}
              rows={4}
              onChange={(e) => setForm({ ...form, text: e.target.value })}
              className="rounded-lg border bg-background px-3 py-2 text-sm"
              data-testid="symptom-text"
            />
            <span className="text-xs text-muted-foreground">{s.describeHint}</span>
          </label>
          <Choice legend={s.since} name="since" options={s.sinceOptions} value={form.since} onChange={(since) => setForm({ ...form, since })} />
          <Choice
            legend={s.severity}
            name="severity"
            options={s.noteLabels.severity}
            value={form.severity}
            onChange={(severity) => setForm({ ...form, severity })}
          />
          <Choice
            legend={s.age}
            name="age"
            options={s.noteLabels.age}
            value={form.age_group}
            onChange={(age_group) => setForm({ ...form, age_group })}
          />
          {form.age_group !== "child" && (
            <Choice
              legend={s.pregnant}
              name="pregnant"
              options={s.noteLabels.pregnant}
              value={form.pregnant}
              onChange={(pregnant) => setForm({ ...form, pregnant })}
            />
          )}
          <p className="rounded-lg border bg-muted/40 p-3 text-xs" data-testid="gemini-notice">
            {s.privacy}
          </p>
          {error && (
            <p className="text-sm text-destructive" role="alert">
              {error}
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            <Button size="lg" onClick={submit} disabled={!answers || sending}>
              {sending && <Loader2 aria-hidden className="animate-spin" />}
              {sending ? s.sending : s.submit}
            </Button>
            <Button size="lg" variant="ghost" onClick={() => go("checklist")}>
              <ArrowLeft aria-hidden />
              {s.backToChecklist}
            </Button>
          </div>
        </section>
      )}

      {step === "result" && result?.data.specialty && (
        <section className="space-y-5" aria-labelledby="result" data-testid="guide-result">
          <Card>
            <CardContent className="space-y-2">
              <h2 id="result" className="text-lg font-semibold">
                {s.resultTitle}
              </h2>
              <p className="text-base font-medium" data-testid="specialty">
                {s.startWith(result.data.specialty.name)}
              </p>
              <p className="text-sm text-muted-foreground">{result.data.specialty.covers}</p>
              {result.data.rule === "child" && <p className="text-sm">{s.ruleChild}</p>}
              {result.data.rule === "pregnant" && <p className="text-sm">{s.rulePregnant}</p>}
              {result.data.specialty.id !== "general_medicine" && general && <p className="text-sm">{s.unsure}</p>}
            </CardContent>
          </Card>

          <Card className="print:hidden">
            <CardContent className="space-y-3">
              <div className="space-y-0.5">
                <h3 className="font-semibold">{s.noteTitle}</h3>
                <p className="text-sm font-medium" data-testid="note-label">
                  {s.noteLabel}
                </p>
                <p className="text-xs text-muted-foreground">
                  {result.data.note_written_by === "answers" ? `${s.noteFromWords} ` : ""}
                  {s.noteEdit}
                </p>
              </div>
              <label className="grid gap-1 text-sm">
                <span>{s.noteLabels.mainProblem}</span>
                <input
                  value={note.main}
                  onChange={(e) => setNote({ ...note, main: e.target.value })}
                  className="h-9 rounded-lg border bg-background px-3"
                  data-testid="note-main"
                />
              </label>
              <label className="grid gap-1 text-sm">
                <span>{s.noteLabels.duration}</span>
                <input
                  value={note.duration}
                  onChange={(e) => setNote({ ...note, duration: e.target.value })}
                  className="h-9 rounded-lg border bg-background px-3"
                />
              </label>
              <label className="grid gap-1 text-sm">
                <span>{s.otherSymptomsField}</span>
                <textarea
                  value={note.others}
                  rows={3}
                  onChange={(e) => setNote({ ...note, others: e.target.value })}
                  className="rounded-lg border bg-background px-3 py-2"
                />
              </label>
              <label className={cn("flex items-center gap-2 text-sm", list.items.length === 0 && "opacity-60")}>
                <input
                  type="checkbox"
                  checked={includeMeds}
                  disabled={list.items.length === 0}
                  onChange={(e) => setIncludeMeds(e.target.checked)}
                  className="size-4"
                  data-testid="include-meds"
                />
                {s.includeMeds}
              </label>
              {list.items.length === 0 && <p className="text-xs text-muted-foreground">{s.noMeds}</p>}
            </CardContent>
          </Card>

          {shared && (
            <>
              <pre
                className="whitespace-pre-wrap rounded-lg border bg-muted/30 p-3 font-sans text-sm"
                data-testid="note-preview"
              >
                {shared}
              </pre>
              <ShareActions title={s.noteTitle} text={shared} url="/symptoms" />
            </>
          )}
          <p className="text-sm font-medium">{t.disclaimer}</p>
          <Button variant="outline" onClick={restart} className="print:hidden">
            <RotateCcw aria-hidden />
            {s.startAgain}
          </Button>
        </section>
      )}
    </div>
  );
}
