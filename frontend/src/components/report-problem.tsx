"use client";

import { Check, Flag, Loader2 } from "lucide-react";
import { useId, useState } from "react";

import { Button } from "@/components/ui/button";
import { useDict } from "@/i18n/client";
import { api, isRateLimited, type ReportReason } from "@/lib/api";

const REASONS: ReportReason[] = ["wrong_price", "not_sold", "wrong_manufacturer", "other"];

type Status = "closed" | "open" | "sending" | "sent" | "enough" | "failed";

/**
 * "Report a problem" with one brand's data. Only the brand and a fixed reason are sent (no free
 * text, nothing about the person); the team checks the brand and fixes the seed data.
 */
export function ReportProblem({ brandId, brandName }: { brandId: number; brandName: string }) {
  const r = useDict().report;
  const [status, setStatus] = useState<Status>("closed");
  const [reason, setReason] = useState<ReportReason | null>(null);
  const id = useId();

  async function send() {
    if (!reason) return;
    setStatus("sending");
    try {
      await api.reportProblem(brandId, reason);
      setStatus("sent");
    } catch (error) {
      setStatus(isRateLimited(error) ? "enough" : "failed");
    }
  }

  if (status === "sent" || status === "enough") {
    return (
      <p className="flex items-center gap-1.5 text-sm font-medium text-primary print:hidden" role="status" data-testid="report-done">
        <Check aria-hidden className="size-4" />
        {status === "sent" ? r.thanks : r.enough}
      </p>
    );
  }

  if (status === "closed") {
    return (
      <Button
        variant="ghost"
        size="sm"
        className="text-muted-foreground print:hidden"
        onClick={() => setStatus("open")}
        aria-label={r.buttonFor(brandName)}
        data-testid="report-button"
      >
        <Flag aria-hidden />
        {r.button}
      </Button>
    );
  }

  return (
    <fieldset className="w-full space-y-2 rounded-lg border p-3 print:hidden" data-testid="report-form">
      <legend className="px-1 text-sm font-medium">{r.title(brandName)}</legend>
      <div className="grid gap-1">
        {REASONS.map((key) => (
          <label key={key} className="flex cursor-pointer items-center gap-2 text-sm">
            <input
              type="radio"
              name={`${id}-reason`}
              value={key}
              checked={reason === key}
              onChange={() => setReason(key)}
              className="size-4 accent-[var(--primary)]"
            />
            {r.reasons[key]}
          </label>
        ))}
      </div>
      <p className="text-xs text-muted-foreground">{r.onlyBrand}</p>
      {status === "failed" && (
        <p className="text-sm text-destructive" role="alert">
          {r.failed}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <Button size="sm" onClick={send} disabled={!reason || status === "sending"}>
          {status === "sending" && <Loader2 aria-hidden className="animate-spin" />}
          {r.send}
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setStatus("closed")}>
          {r.cancel}
        </Button>
      </div>
    </fieldset>
  );
}
