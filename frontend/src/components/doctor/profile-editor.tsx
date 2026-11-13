"use client";

import { Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useDict } from "@/i18n/client";
import { doctorApi, type DoctorChamberIn, type DoctorProfile } from "@/lib/api";

import { errorText, Field, FormMessage, StatusCard, useDoctor } from "./shared";

const MAX_CHAMBERS = 3;
const EMPTY_CHAMBER: DoctorChamberIn = { name: "", address: "", hours: "", phone: null };

function ProfileForm({ doctor, onSaved }: { doctor: DoctorProfile; onSaved: (d: DoctorProfile) => void }) {
  const t = useDict();
  const f = t.doctor.fields;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const text = (name: string) => String(form.get(name) ?? "").trim();
    setBusy(true);
    setError(null);
    setOk(null);
    try {
      onSaved(
        await doctorApi.saveProfile({
          display_name: text("display_name"),
          display_name_bn: text("display_name_bn") || null,
          degrees: text("degrees"),
          specialty: text("specialty"),
          bmdc_number: text("bmdc_number"),
          phone: text("phone") || null,
        }),
      );
      setOk(t.doctor.profileSaved);
    } catch (e) {
      setError(errorText(t, e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} className="space-y-4" data-testid="profile-form">
      <Field id="display_name" label={f.name} defaultValue={doctor.display_name} required maxLength={120} />
      <Field id="display_name_bn" label={f.nameBn} lang="bn" defaultValue={doctor.display_name_bn ?? ""} maxLength={120} />
      <Field id="degrees" label={f.degrees} defaultValue={doctor.degrees} required maxLength={200} />
      <Field id="specialty" label={f.specialty} defaultValue={doctor.specialty} required maxLength={120} />
      <Field
        id="bmdc_number"
        label={f.bmdc}
        defaultValue={doctor.bmdc_number}
        required
        maxLength={20}
        pattern="[A-Za-z0-9\-]+"
      />
      <Field id="phone" label={f.phone} type="tel" defaultValue={doctor.phone ?? ""} maxLength={20} />
      <p className="text-xs text-muted-foreground">{t.doctor.recheckNote}</p>
      <FormMessage error={error} ok={ok} />
      <Button type="submit" disabled={busy}>
        {busy ? t.doctor.working : t.doctor.profileSave}
      </Button>
    </form>
  );
}

function ChambersForm({ doctor, onSaved }: { doctor: DoctorProfile; onSaved: (d: DoctorProfile) => void }) {
  const t = useDict();
  const [chambers, setChambers] = useState<DoctorChamberIn[]>(doctor.chambers);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const change = (index: number, field: keyof DoctorChamberIn, value: string) =>
    setChambers((list) => list.map((c, i) => (i === index ? { ...c, [field]: value } : c)));
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setOk(null);
    try {
      const saved = await doctorApi.saveChambers(
        chambers.map((c) => ({ ...c, phone: c.phone?.trim() ? c.phone.trim() : null })),
      );
      onSaved(saved);
      setChambers(saved.chambers);
      setOk(t.doctor.chambersSaved);
    } catch (e) {
      setError(errorText(t, e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} className="space-y-4" data-testid="chambers-form">
      {chambers.length === 0 && <p className="text-sm text-muted-foreground">{t.doctor.noChambers}</p>}
      {chambers.map((c, i) => {
        const n = t.fmt.int(i + 1);
        return (
          <fieldset key={i} className="space-y-3 rounded-lg border p-3">
            <legend className="px-1 text-sm font-medium">{t.doctor.chamber(n)}</legend>
            <Field
              id={`chamber-${i}-name`}
              label={t.doctor.chamberName}
              value={c.name}
              onChange={(e) => change(i, "name", e.target.value)}
              required
              maxLength={120}
            />
            <Field
              id={`chamber-${i}-address`}
              label={t.doctor.chamberAddress}
              value={c.address}
              onChange={(e) => change(i, "address", e.target.value)}
              required
              maxLength={300}
            />
            <Field
              id={`chamber-${i}-hours`}
              label={t.doctor.chamberHours}
              hint={t.doctor.chamberHoursHint}
              value={c.hours}
              onChange={(e) => change(i, "hours", e.target.value)}
              required
              maxLength={200}
            />
            <Field
              id={`chamber-${i}-phone`}
              label={t.doctor.chamberPhone}
              type="tel"
              value={c.phone ?? ""}
              onChange={(e) => change(i, "phone", e.target.value)}
              maxLength={20}
            />
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setChambers((list) => list.filter((_, j) => j !== i))}
            >
              <Trash2 aria-hidden />
              {t.doctor.removeChamber}
            </Button>
          </fieldset>
        );
      })}
      <div className="flex flex-wrap gap-2">
        {chambers.length < MAX_CHAMBERS && (
          <Button type="button" variant="outline" onClick={() => setChambers((list) => [...list, { ...EMPTY_CHAMBER }])}>
            <Plus aria-hidden />
            {t.doctor.addChamber}
          </Button>
        )}
        <Button type="submit" disabled={busy}>
          {busy ? t.doctor.working : t.doctor.chambersSave}
        </Button>
      </div>
      <FormMessage error={error} ok={ok} />
    </form>
  );
}

export function ProfileEditor() {
  const t = useDict();
  const { state, setState } = useDoctor();
  if (state.kind === "loading") return <Skeleton className="h-60 w-full" />;
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
  const onSaved = (doctor: DoctorProfile) => setState({ kind: "in", doctor });
  return (
    <div className="space-y-8">
      <StatusCard doctor={state.doctor} />
      <section className="space-y-3">
        <h2 className="text-lg font-semibold">{t.doctor.profileTitle}</h2>
        <ProfileForm doctor={state.doctor} onSaved={onSaved} />
      </section>
      <section className="space-y-3">
        <h2 className="text-lg font-semibold">{t.doctor.chambersTitle}</h2>
        <ChambersForm doctor={state.doctor} onSaved={onSaved} />
      </section>
    </div>
  );
}
