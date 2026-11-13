"use client";

import { BadgeCheck, Clock, FlaskConical, ShieldAlert } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useDict } from "@/i18n/client";
import type { Dict } from "@/i18n/dictionaries";
import { ApiError, doctorApi, type DoctorProfile } from "@/lib/api";

export type DoctorState = { kind: "loading" } | { kind: "out" } | { kind: "in"; doctor: DoctorProfile };

/** The logged-in doctor (from the HttpOnly session cookie, via /api/doctor/me). */
export function useDoctor() {
  const [state, setState] = useState<DoctorState>({ kind: "loading" });
  const refresh = useCallback(async () => {
    try {
      setState({ kind: "in", doctor: await doctorApi.me() });
    } catch {
      setState({ kind: "out" });
    }
  }, []);
  useEffect(() => {
    // Ask once on load; the answer depends on the cookie, which only the server can read.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
  }, [refresh]);
  return { state, setState, refresh };
}

/** The message for an error from the doctor API, in the page language. */
export function errorText(t: Dict, error: unknown): string {
  const messages = t.doctor.errors as Record<string, string>;
  if (error instanceof ApiError) {
    if (error.status === 422 && !(error.code in messages)) return messages.validation_error;
    return messages[error.code] ?? messages.generic;
  }
  return messages.generic;
}

export function Field({
  id,
  label,
  hint,
  ...input
}: { id: string; label: string; hint?: string } & React.ComponentProps<"input">) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} name={id} aria-describedby={hint ? `${id}-hint` : undefined} {...input} />
      {hint && (
        <p id={`${id}-hint`} className="text-xs text-muted-foreground">
          {hint}
        </p>
      )}
    </div>
  );
}

export function FormMessage({ error, ok }: { error?: string | null; ok?: string | null }) {
  if (error) {
    return (
      <p role="alert" className="text-sm text-destructive">
        {error}
      </p>
    );
  }
  if (ok) {
    return (
      <p role="status" className="text-sm text-emerald-700 dark:text-emerald-400">
        {ok}
      </p>
    );
  }
  return null;
}

/** Pending, verified (badge), rejected (with the reason) or demo. */
export function StatusCard({ doctor }: { doctor: DoctorProfile }) {
  const t = useDict();
  const s = t.doctor.status;
  const [Icon, title, text, tone] = doctor.is_demo
    ? [FlaskConical, s.demo, s.demoText, "border-violet-300 bg-violet-50 dark:border-violet-800 dark:bg-violet-950/40"]
    : doctor.status === "verified"
      ? [
          BadgeCheck,
          s.verified,
          doctor.verified_on ? s.verifiedText(t.fmt.date(new Date(doctor.verified_on))) : "",
          "border-emerald-300 bg-emerald-50 dark:border-emerald-800 dark:bg-emerald-950/40",
        ]
      : doctor.status === "rejected"
        ? [
            ShieldAlert,
            s.rejected,
            s.rejectedText(doctor.rejection_reason ?? ""),
            "border-red-300 bg-red-50 dark:border-red-800 dark:bg-red-950/40",
          ]
        : [Clock, s.pending, s.pendingText, "border-amber-300 bg-amber-50 dark:border-amber-700 dark:bg-amber-950/40"];
  return (
    <div className={`flex gap-3 rounded-lg border p-3 ${tone}`} data-testid="doctor-status">
      <Icon aria-hidden className="mt-0.5 size-5 shrink-0" />
      <div className="space-y-1">
        <p className="font-medium">{title}</p>
        {text && <p className="text-sm text-muted-foreground">{text}</p>}
      </div>
    </div>
  );
}
