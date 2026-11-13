"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { useDict } from "@/i18n/client";
import { doctorApi } from "@/lib/api";

import { errorText, Field, FormMessage } from "./shared";

/**
 * The one-time link from the owner is /doctor/reset#<token>. The part after # never reaches any
 * server (or its logs); it is read here, removed from the address bar, and sent once in the body.
 */
export function ResetForm() {
  const t = useDict();
  const f = t.doctor.fields;
  const [token, setToken] = useState<string | null | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    const fromHash = window.location.hash.slice(1);
    window.history.replaceState(null, "", window.location.pathname);
    // The token exists only in the address bar, which the server render cannot see.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setToken(fromHash.length >= 20 ? fromHash : null);
  }, []);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const next = String(form.get("new-password") ?? "");
    setError(null);
    if (next !== String(form.get("confirm-password") ?? "")) {
      setError(t.doctor.mismatch);
      return;
    }
    setBusy(true);
    try {
      await doctorApi.resetPassword(token ?? "", next);
      setDone(true);
    } catch (e) {
      setError(errorText(t, e));
    } finally {
      setBusy(false);
    }
  }

  if (token === undefined) return null;
  if (token === null) return <FormMessage error={t.doctor.resetMissing} />;
  if (done) {
    return (
      <div className="space-y-2">
        <FormMessage ok={t.doctor.resetDone} />
        <Link href="/doctor" className="text-sm underline underline-offset-2">
          {t.doctor.loginButton}
        </Link>
      </div>
    );
  }
  return (
    <form onSubmit={submit} className="space-y-4" data-testid="reset-form">
      <p className="text-sm text-muted-foreground">{t.doctor.resetText}</p>
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
      <FormMessage error={error} />
      <Button type="submit" disabled={busy}>
        {busy ? t.doctor.working : t.doctor.resetButton}
      </Button>
    </form>
  );
}
