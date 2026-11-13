"use client";

import { Pencil, Plus, Trash2, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useDict } from "@/i18n/client";
import { doctorApi, type TemplateSummary } from "@/lib/api";

import { errorText, FormMessage, useDoctor } from "./shared";

const MAX_FAVOURITES = 50;

function Templates() {
  const t = useDict();
  const p = t.doctor.templatesPage;
  const [list, setList] = useState<TemplateSummary[] | null>(null);
  const [renaming, setRenaming] = useState<{ id: number; name: string } | null>(null);
  const [deleting, setDeleting] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    doctorApi.templates().then((items) => active && setList(items)).catch((e) => active && setError(errorText(t, e)));
    return () => {
      active = false;
    };
  }, [t]);

  async function run(action: () => Promise<unknown>) {
    setError(null);
    try {
      await action();
      setList(await doctorApi.templates());
      setRenaming(null);
      setDeleting(null);
    } catch (e) {
      setError(errorText(t, e));
    }
  }

  if (list === null) return error ? <FormMessage error={error} /> : <Skeleton className="h-24 w-full" />;
  return (
    <section className="space-y-3" data-testid="templates-list">
      {list.length === 0 && <p className="text-sm text-muted-foreground">{p.empty}</p>}
      <ul className="space-y-2">
        {list.map((item) => (
          <li key={item.id} className="space-y-2 rounded-lg border p-3">
            {renaming?.id === item.id ? (
              <div className="flex flex-wrap gap-2">
                <Input
                  aria-label={p.rename}
                  value={renaming.name}
                  maxLength={60}
                  autoComplete="off"
                  spellCheck={false}
                  onChange={(e) => setRenaming({ id: item.id, name: e.target.value })}
                  className="min-w-0 flex-1"
                />
                <Button size="sm" disabled={!renaming.name.trim()} onClick={() => run(() => doctorApi.renameTemplate(item.id, renaming.name))}>
                  {p.renameSave}
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setRenaming(null)}>
                  {p.cancel}
                </Button>
              </div>
            ) : (
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="font-medium">{item.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {p.lines(t.fmt.int(item.line_count))} · {p.changed(t.fmt.date(new Date(item.updated_at)))}
                  </p>
                </div>
                <div className="flex gap-1">
                  <Button size="sm" variant="ghost" onClick={() => setRenaming({ id: item.id, name: item.name })}>
                    <Pencil aria-hidden />
                    {p.rename}
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setDeleting(item.id)}>
                    <Trash2 aria-hidden />
                    {p.delete}
                  </Button>
                </div>
              </div>
            )}
            {deleting === item.id && (
              <div className="flex flex-wrap items-center gap-2 text-sm">
                {p.deleteConfirm(item.name)}
                <Button size="sm" variant="destructive" onClick={() => run(() => doctorApi.deleteTemplate(item.id))}>
                  {p.deleteYes}
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setDeleting(null)}>
                  {p.cancel}
                </Button>
              </div>
            )}
          </li>
        ))}
      </ul>
      <FormMessage error={error} />
    </section>
  );
}

function Favourites() {
  const t = useDict();
  const p = t.doctor.templatesPage;
  const [tests, setTests] = useState<string[] | null>(null);
  const [draft, setDraft] = useState("");
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    let active = true;
    doctorApi.favouriteTests().then((data) => active && setTests(data.tests)).catch(() => active && setTests([]));
    return () => {
      active = false;
    };
  }, []);

  async function save(next: string[]) {
    setMessage(null);
    try {
      setTests((await doctorApi.saveFavouriteTests(next)).tests);
      setMessage({ ok: true, text: p.saved });
    } catch (e) {
      setMessage({ ok: false, text: errorText(t, e) });
    }
  }

  if (tests === null) return <Skeleton className="h-16 w-full" />;
  const full = tests.length >= MAX_FAVOURITES;
  return (
    <section className="space-y-3" data-testid="favourite-tests">
      <h2 className="text-lg font-semibold">{p.favTitle}</h2>
      <p className="text-sm text-muted-foreground">{p.favHint}</p>
      <ul className="flex flex-wrap gap-1.5">
        {tests.map((test) => (
          <li key={test}>
            <span className="inline-flex items-center gap-1 rounded-full bg-secondary px-2.5 py-1 text-sm">
              {test}
              <button
                type="button"
                aria-label={p.favRemove(test)}
                className="rounded-full p-0.5 hover:bg-muted"
                onClick={() => void save(tests.filter((x) => x !== test))}
              >
                <X aria-hidden className="size-3.5" />
              </button>
            </span>
          </li>
        ))}
      </ul>
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (draft.trim()) void save([...tests, draft.trim()]).then(() => setDraft(""));
        }}
      >
        <Input
          aria-label={p.favPlaceholder}
          placeholder={p.favPlaceholder}
          value={draft}
          maxLength={80}
          disabled={full}
          autoComplete="off"
          spellCheck={false}
          onChange={(e) => setDraft(e.target.value)}
          className="min-w-0 flex-1"
        />
        <Button type="submit" size="sm" disabled={full || !draft.trim()}>
          <Plus aria-hidden />
          {p.favAdd}
        </Button>
      </form>
      {full && <p className="text-xs text-muted-foreground">{p.favFull}</p>}
      {message && <FormMessage error={message.ok ? null : message.text} ok={message.ok ? message.text : null} />}
    </section>
  );
}

export function TemplatesManager() {
  const t = useDict();
  const { state } = useDoctor();
  if (state.kind === "loading") return <Skeleton className="h-40 w-full" />;
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
  return (
    <div className="space-y-8">
      <p className="text-sm text-muted-foreground">{t.doctor.templatesPage.intro}</p>
      <Templates />
      <Favourites />
    </div>
  );
}
