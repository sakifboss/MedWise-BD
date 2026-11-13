"use client";

import { LogOut } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useDict } from "@/i18n/client";
import { doctorApi, type DoctorProfile } from "@/lib/api";

import { errorText, Field, FormMessage, StatusCard, useDoctor } from "./shared";

function LoginForm({ onDone }: { onDone: (doctor: DoctorProfile) => void }) {
  const t = useDict();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError(null);
    try {
      onDone(await doctorApi.login(String(form.get("login-email")), String(form.get("login-password"))));
    } catch (e) {
      setError(errorText(t, e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} className="space-y-4" data-testid="login-form">
      <Field id="login-email" label={t.doctor.fields.email} type="email" autoComplete="username" required />
      <Field
        id="login-password"
        label={t.doctor.fields.password}
        type="password"
        autoComplete="current-password"
        required
      />
      <FormMessage error={error} />
      <Button type="submit" disabled={busy}>
        {busy ? t.doctor.working : t.doctor.loginButton}
      </Button>
      <p className="text-xs text-muted-foreground">{t.doctor.forgot}</p>
    </form>
  );
}

function SignupForm({ onDone }: { onDone: (doctor: DoctorProfile) => void }) {
  const t = useDict();
  const f = t.doctor.fields;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const text = (name: string) => String(form.get(name) ?? "").trim();
    setBusy(true);
    setError(null);
    try {
      onDone(
        await doctorApi.signup({
          email: text("email"),
          password: String(form.get("password") ?? ""),
          display_name: text("display_name"),
          display_name_bn: text("display_name_bn") || null,
          degrees: text("degrees"),
          specialty: text("specialty"),
          bmdc_number: text("bmdc_number"),
          phone: text("phone") || null,
        }),
      );
    } catch (e) {
      setError(errorText(t, e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} className="space-y-4" data-testid="signup-form">
      <Field id="email" label={f.email} type="email" autoComplete="email" required maxLength={254} />
      <Field
        id="password"
        label={f.password}
        hint={f.passwordHint}
        type="password"
        autoComplete="new-password"
        required
        minLength={10}
        maxLength={128}
      />
      <Field id="display_name" label={f.name} hint={f.nameHint} autoComplete="name" required maxLength={120} />
      <Field id="display_name_bn" label={f.nameBn} lang="bn" maxLength={120} />
      <Field id="degrees" label={f.degrees} hint={f.degreesHint} required maxLength={200} />
      <Field id="specialty" label={f.specialty} required maxLength={120} />
      <Field id="bmdc_number" label={f.bmdc} hint={f.bmdcHint} required maxLength={20} pattern="[A-Za-z0-9\-]+" />
      <Field id="phone" label={f.phone} type="tel" autoComplete="tel" maxLength={20} />
      <label className="flex items-start gap-2 text-sm">
        <input type="checkbox" required className="mt-1 size-4 shrink-0" name="agree" />
        <span>
          {t.doctor.agree}{" "}
          <Link href="/doctor/privacy" className="underline underline-offset-2">
            {t.doctor.privacyLink}
          </Link>
        </span>
      </label>
      <p className="text-xs text-muted-foreground">{t.doctor.privacyNote}</p>
      <FormMessage error={error} />
      <Button type="submit" disabled={busy}>
        {busy ? t.doctor.working : t.doctor.signupButton}
      </Button>
    </form>
  );
}

export function DoctorHome() {
  const t = useDict();
  const { state, setState } = useDoctor();
  const [tab, setTab] = useState<"login" | "signup">("login");
  const [message, setMessage] = useState<string | null>(null);

  if (state.kind === "loading") return <Skeleton className="h-40 w-full" />;

  if (state.kind === "in") {
    const doctor = state.doctor;
    async function logout() {
      try {
        await doctorApi.logout();
      } finally {
        setState({ kind: "out" });
        setMessage(t.doctor.loggedOut);
      }
    }
    return (
      <section className="space-y-4" data-testid="doctor-summary">
        <p className="font-medium">{t.doctor.loggedInAs(doctor.display_name)}</p>
        <StatusCard doctor={doctor} />
        <nav className="flex flex-wrap gap-2">
          <Link href="/doctor/profile" className={buttonVariants({ variant: "outline" })}>
            {t.doctor.profileLink}
          </Link>
          <Link href="/doctor/account" className={buttonVariants({ variant: "outline" })}>
            {t.doctor.accountLink}
          </Link>
          <Button variant="ghost" onClick={logout}>
            <LogOut aria-hidden />
            {t.doctor.logout}
          </Button>
        </nav>
      </section>
    );
  }

  return (
    <section className="space-y-4">
      <FormMessage ok={message} />
      <div role="tablist" className="inline-flex rounded-lg border p-0.5">
        {(["login", "signup"] as const).map((key) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={tab === key}
            onClick={() => setTab(key)}
            className={`rounded-md px-3 py-1.5 text-sm font-medium ${tab === key ? "bg-primary text-primary-foreground" : "text-muted-foreground"}`}
          >
            {t.doctor.tabs[key]}
          </button>
        ))}
      </div>
      {tab === "login" ? (
        <LoginForm onDone={(doctor) => setState({ kind: "in", doctor })} />
      ) : (
        <SignupForm onDone={(doctor) => setState({ kind: "in", doctor })} />
      )}
    </section>
  );
}
