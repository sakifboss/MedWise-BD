"use client";

import { Check, Loader2, Plus } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { useDict } from "@/i18n/client";
import { api, isRateLimited, type RequestSource } from "@/lib/api";

type Status = "idle" | "sending" | "sent" | "failed" | "enough";

// One stats call per page load, shared by every request box on the page.
let generics: Promise<number | null> | null = null;
function genericCount(): Promise<number | null> {
  generics ??= api.stats().then(
    (s) => s.generics,
    () => {
      generics = null; // try again next time
      return null;
    },
  );
  return generics;
}

/**
 * Shown when we have no data for a medicine: says how many we cover and lets the person ask us
 * to add it. Only the text and where it came from are sent; nothing about the person.
 */
export function RequestMedicine({ query, source }: { query: string; source: RequestSource }) {
  const t = useDict();
  const r = t.request;
  const [count, setCount] = useState<number | null>(null);
  const [status, setStatus] = useState<Status>("idle");

  useEffect(() => {
    let active = true;
    genericCount().then((n) => active && setCount(n));
    return () => {
      active = false;
    };
  }, []);

  async function send() {
    setStatus("sending");
    try {
      await api.requestMedicine(query, source);
      setStatus("sent");
    } catch (error) {
      setStatus(isRateLimited(error) ? "enough" : "failed");
    }
  }

  return (
    <div className="space-y-2 text-sm" data-testid="request-medicine">
      {count !== null && <p className="text-muted-foreground">{r.covered(t.fmt.int(count))}</p>}
      {status === "sent" ? (
        <p className="flex items-center gap-1.5 font-medium text-primary" role="status">
          <Check aria-hidden className="size-4" />
          {r.thanks}
        </p>
      ) : status === "enough" ? (
        <p role="status">{r.enough}</p>
      ) : (
        <div className="space-y-1">
          <Button variant="outline" size="sm" onClick={send} disabled={status === "sending"}>
            {status === "sending" ? (
              <Loader2 aria-hidden className="animate-spin" />
            ) : (
              <Plus aria-hidden />
            )}
            {status === "sending" ? r.sending : r.button}
          </Button>
          <p className="text-xs text-muted-foreground">{r.onlyName}</p>
          {status === "failed" && (
            <p className="text-destructive" role="alert">
              {r.failed}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
