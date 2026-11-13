"use client";

import { Download, LogOut, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useDict } from "@/i18n/client";
import { doctorApi } from "@/lib/api";

import { errorText, Field, FormMessage, useDoctor } from "./shared";

function PasswordForm() {
  const t = useDict();
  const f = t.doctor.fields;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const next = String(form.get("new-password") ?? "");
    setError(null);
    setOk(null);
    if (next !== String(form.get("confirm-password") ?? "")) {
      setError(t.doctor.mismatch);
      return;
    }
    setBusy(true);
    try {
      await doctorApi.changePassword(String(form.get("current-password") ?? ""), next);
      formElement.reset();
      setOk(t.doctor.passwordSaved);
    } catch (e) {
      setError(errorText(t, e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} className="space-y-4" data-testid="password-form">
      <Field id="current-password" label={f.currentPassword} type="password" autoComplete="current-password" required />
      <Field
        id="new-password"
        label={f.newPassword}
        hint={f.passwordHint}
        type="password"
        autoComplete="new-password"
        required
        minLength={10}
        maxLength={128}
      />
      <Field id="confirm-password" label={f.confirmPassword} type="password" autoComplete="new-password" required />
      <FormMessage error={error} ok={ok} />
      <Button type="submit" disabled={busy}>
        {busy ? t.doctor.working : t.doctor.passwordSave}
      </Button>
    </form>
  );
}

/** Downloads the export as a file made on the device (nothing else is sent anywhere). */
async function downloadData(): Promise<void> {
  const data = await doctorApi.exportData();
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `medwise-doctor-data-${data.exported_on}.json`;
  link.click();
  URL.revokeObjectURL(url);
}

export function AccountPanel() {
  const t = useDict();
  const { state, setState } = useDoctor();
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  if (state.kind === "loading") return <Skeleton className="h-60 w-full" />;
  if (state.kind === "out") {
    return (
      <div className="space-y-2">
        <FormMessage ok={message} />
        <p className="text-sm">
          {message ? null : `${t.doctor.needLogin} `}
          <Link href="/doctor" className="underline underline-offset-2">
            {t.doctor.title}
          </Link>
        </p>
      </div>
    );
  }

  async function run(action: () => Promise<unknown>, done?: string, loggedOut = false) {
    setBusy(true);
    setError(null);
    try {
      await action();
      if (loggedOut) setState({ kind: "out" });
      if (done) setMessage(done);
    } catch (e) {
      setError(errorText(t, e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <h2 className="text-lg font-semibold">{t.doctor.passwordTitle}</h2>
        <PasswordForm />
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">{t.doctor.logoutAll}</h2>
        <p className="text-sm text-muted-foreground">{t.doctor.logoutAllText}</p>
        <Button
          variant="outline"
          disabled={busy}
          onClick={() => run(() => doctorApi.logoutEverywhere(), t.doctor.loggedOut, true)}
        >
          <LogOut aria-hidden />
          {t.doctor.logoutAll}
        </Button>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">{t.doctor.dataTitle}</h2>
        <p className="text-sm text-muted-foreground">{t.doctor.dataText}</p>
        <Button variant="outline" disabled={busy} onClick={() => run(downloadData)}>
          <Download aria-hidden />
          {t.doctor.download}
        </Button>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">{t.doctor.deleteTitle}</h2>
        <p className="text-sm text-muted-foreground">{t.doctor.deleteText}</p>
        {confirming && (
          <div className="space-y-2">
            <p className="text-sm">{t.doctor.deleteConfirm}</p>
            <Field
              id="delete-password"
              label={t.doctor.fields.password}
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
        )}
        <Button
          variant="destructive"
          disabled={busy || (confirming && !password)}
          onClick={() =>
            confirming
              ? run(() => doctorApi.deleteAccount(password), t.doctor.deleted, true)
              : setConfirming(true)
          }
        >
          <Trash2 aria-hidden />
          {t.doctor.deleteButton}
        </Button>
      </section>

      <FormMessage error={error} ok={message} />
    </div>
  );
}
