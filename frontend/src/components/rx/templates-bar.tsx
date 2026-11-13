"use client";

import { BookmarkPlus, Settings2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { errorText } from "@/components/doctor/shared";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useDict } from "@/i18n/client";
import { api, doctorApi, type TemplateOut, type TemplateSummary } from "@/lib/api";
import type { RxLine } from "@/lib/rx";
import { fromTemplateLine, toTemplateLines, type Catalog } from "@/lib/rx-templates";

const SELECT =
  "h-8 min-w-0 flex-1 rounded-lg border border-input bg-transparent px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30";

/**
 * Templates on the pad: apply one, or save the current medicine lines, tests and advice as one.
 * The patient fields are never read here, so they can never end up in a template.
 */
export function TemplatesBar({
  lines,
  tests,
  advice,
  onApply,
}: {
  lines: RxLine[];
  tests: string;
  advice: string;
  /** Called with the template's lines (as pad lines), tests and advice, and lines kept as written. */
  onApply: (t: { name: string; lines: RxLine[]; tests: string; advice: string; asWritten: number }) => void;
}) {
  const t = useDict();
  const c = t.rx.templates;
  const [list, setList] = useState<TemplateSummary[]>([]);
  const [chosen, setChosen] = useState<number | "">("");
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [saving, setSaving] = useState(false);
  const [name, setName] = useState("");
  const [replacing, setReplacing] = useState<TemplateSummary | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    let active = true;
    doctorApi.templates().then((items) => active && setList(items)).catch(() => {});
    Promise.all([api.brandIndex(), api.generics()])
      .then(([index, generics]) => {
        if (active) {
          setCatalog({
            brands: new Map(index.brands.map((b) => [b.code, b])),
            generics: new Map(generics.map((g) => [g.name, g.id])),
          });
        }
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);

  async function apply() {
    if (chosen === "" || !catalog) return;
    setBusy(true);
    setMessage(null);
    try {
      const template: TemplateOut = await doctorApi.template(chosen);
      const converted = template.lines.map((line) => fromTemplateLine(line, catalog, crypto.randomUUID()));
      onApply({
        name: template.name,
        lines: converted.map((x) => x.line),
        tests: template.tests,
        advice: template.advice,
        asWritten: converted.filter((x) => x.asWritten).length,
      });
    } catch (e) {
      setMessage({ ok: false, text: errorText(t, e) });
    } finally {
      setBusy(false);
    }
  }

  async function save(replace?: TemplateSummary) {
    const clean = name.trim().replace(/\s+/g, " ");
    if (!clean) return;
    const existing = list.find((x) => x.name.toLowerCase() === clean.toLowerCase());
    if (existing && !replace) {
      setReplacing(existing);
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      const body = { name: clean, lines: toTemplateLines(lines), tests, advice };
      const saved = replace ? await doctorApi.updateTemplate(replace.id, body) : await doctorApi.createTemplate(body);
      setList(await doctorApi.templates());
      setChosen(saved.id);
      setSaving(false);
      setReplacing(null);
      setName("");
      setMessage({ ok: true, text: c.saved(saved.name) });
    } catch (e) {
      setMessage({ ok: false, text: errorText(t, e) });
    } finally {
      setBusy(false);
    }
  }

  const empty = lines.length === 0 && !tests.trim() && !advice.trim();

  return (
    <section className="space-y-2 rounded-lg border p-3" data-testid="rx-templates">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">{c.title}</h2>
        <Link href="/doctor/templates" className="inline-flex items-center gap-1 text-xs underline underline-offset-2">
          <Settings2 aria-hidden className="size-3.5" />
          {c.manage}
        </Link>
      </div>
      {list.length ? (
        <div className="flex gap-2">
          <label htmlFor="rx-template-choose" className="sr-only">
            {c.choose}
          </label>
          <select
            id="rx-template-choose"
            className={SELECT}
            value={chosen}
            onChange={(e) => setChosen(e.target.value ? Number(e.target.value) : "")}
          >
            <option value="">{c.choose}</option>
            {list.map((x) => (
              <option key={x.id} value={x.id}>
                {x.name}
              </option>
            ))}
          </select>
          <Button size="sm" variant="outline" disabled={chosen === "" || !catalog || busy} onClick={() => void apply()}>
            {c.apply}
          </Button>
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">{c.none}</p>
      )}

      {saving ? (
        <div className="space-y-2 rounded-md bg-muted/50 p-2" data-testid="rx-template-save">
          <p className="text-sm font-medium text-amber-800 dark:text-amber-300">{c.warning}</p>
          <label htmlFor="rx-template-name" className="text-xs font-medium">
            {c.name}
          </label>
          <Input
            id="rx-template-name"
            value={name}
            maxLength={60}
            onChange={(e) => {
              setName(e.target.value);
              setReplacing(null);
            }}
            list="rx-template-names"
            autoComplete="off"
            spellCheck={false}
          />
          <datalist id="rx-template-names">
            {list.map((x) => (
              <option key={x.id} value={x.name} />
            ))}
          </datalist>
          <p className="text-xs text-muted-foreground">{c.willSave(t.fmt.int(lines.length))}</p>
          {replacing ? (
            <div className="flex flex-wrap items-center gap-2 text-sm">
              {c.replace(replacing.name)}
              <Button size="sm" variant="destructive" disabled={busy} onClick={() => void save(replacing)}>
                {c.replaceYes}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setReplacing(null)}>
                {c.cancel}
              </Button>
            </div>
          ) : (
            <div className="flex gap-2">
              <Button size="sm" disabled={busy || !name.trim()} onClick={() => void save()}>
                {c.save}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setSaving(false)}>
                {c.cancel}
              </Button>
            </div>
          )}
        </div>
      ) : (
        <Button size="sm" variant="outline" disabled={empty} onClick={() => setSaving(true)} title={empty ? c.nothingToSave : undefined}>
          <BookmarkPlus aria-hidden />
          {c.saveAs}
        </Button>
      )}
      {message && (
        <p role={message.ok ? "status" : "alert"} className={message.ok ? "text-xs text-emerald-700 dark:text-emerald-400" : "text-xs text-destructive"}>
          {message.text}
        </p>
      )}
    </section>
  );
}

/** The doctor's favourite tests as buttons; a tap adds the test to the Tests box. */
export function FavouriteTestChips({ onPick }: { onPick: (test: string) => void }) {
  const t = useDict();
  const [tests, setTests] = useState<string[]>([]);
  useEffect(() => {
    let active = true;
    doctorApi.favouriteTests().then((data) => active && setTests(data.tests)).catch(() => {});
    return () => {
      active = false;
    };
  }, []);
  if (!tests.length) return null;
  return (
    <div className="space-y-1" data-testid="rx-favourite-tests">
      <p className="text-xs text-muted-foreground">
        {t.rx.favourites.title} · {t.rx.favourites.hint}
      </p>
      <div className="flex flex-wrap gap-1">
        {tests.map((test) => (
          <Button key={test} type="button" size="xs" variant="secondary" onClick={() => onPick(test)}>
            {test}
          </Button>
        ))}
      </div>
    </div>
  );
}
