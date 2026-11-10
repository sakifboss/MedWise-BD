import { CircleAlert, Copy, ShieldQuestion } from "lucide-react";
import Link from "next/link";

import { SeverityBadge } from "@/components/severity-badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useDict } from "@/i18n/client";
import type { FoundInteraction, InteractionCheckResponse, Severity } from "@/lib/api";
import { cn } from "@/lib/utils";

const SEVERITY_ORDER: Severity[] = ["major", "moderate", "minor"];

const CARD_STYLES: Record<Severity, string> = {
  major: "border-red-300 bg-red-50/60 dark:border-red-800 dark:bg-red-950/40",
  moderate: "border-amber-300 bg-amber-50/60 dark:border-amber-700 dark:bg-amber-950/40",
  minor: "border-border",
};

function Summary({ data }: { data: InteractionCheckResponse }) {
  const t = useDict();
  const counts = SEVERITY_ORDER.map((s) => [s, data.interactions.filter((i) => i.severity === s).length] as const)
    .filter(([, n]) => n > 0);
  const total = data.interactions.length;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <p className="font-medium">
        {total === 0 ? t.interactions.noneRecorded : t.interactions.found(total)}
      </p>
      {counts.map(([severity, n]) => (
        <span key={severity} className="inline-flex items-center gap-1 text-sm">
          <SeverityBadge severity={severity} />
          <span className="tabular-nums text-muted-foreground">×{t.fmt.int(n)}</span>
        </span>
      ))}
    </div>
  );
}

function InteractionCard({ interaction }: { interaction: FoundInteraction }) {
  const { generic_a: a, generic_b: b } = interaction;
  return (
    <li className={cn("space-y-1 rounded-lg border p-3", CARD_STYLES[interaction.severity])}>
      <div className="flex flex-wrap items-center gap-2">
        <p className="font-medium">
          <Link href={`/generics/${a.id}`} className="underline-offset-4 hover:underline">
            {a.name}
          </Link>{" "}
          +{" "}
          <Link href={`/generics/${b.id}`} className="underline-offset-4 hover:underline">
            {b.name}
          </Link>
        </p>
        <SeverityBadge severity={interaction.severity} />
      </div>
      <p className="text-sm text-muted-foreground">{interaction.description}</p>
    </li>
  );
}

export function InteractionResults({ data }: { data: InteractionCheckResponse }) {
  const copy = useDict().interactions;
  return (
    <div className="space-y-3">
      {data.duplicates.map((d) => (
        <Alert key={d.generic_id} className="border-amber-300 bg-amber-50 text-amber-950 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-100">
          <Copy aria-hidden />
          <AlertTitle>{copy.duplicateTitle}</AlertTitle>
          <AlertDescription className="text-amber-900 dark:text-amber-200">{copy.duplicateText(d.brands, d.generic_name)}</AlertDescription>
        </Alert>
      ))}

      {data.medicines.length < 2 ? (
        <p className="text-sm text-muted-foreground">{copy.addAtLeastTwo}</p>
      ) : (
        <>
          <Summary data={data} />
          {data.interactions.length > 0 && (
            <ul className="space-y-2">
              {data.interactions.map((x) => (
                <InteractionCard key={`${x.generic_a.id}-${x.generic_b.id}`} interaction={x} />
              ))}
            </ul>
          )}
          <p className="flex gap-2 text-xs text-muted-foreground">
            {data.interactions.length ? (
              <CircleAlert aria-hidden className="size-4 shrink-0" />
            ) : (
              <ShieldQuestion aria-hidden className="size-4 shrink-0" />
            )}
            {copy.note}
          </p>
          <p className="text-xs text-muted-foreground">
            {copy.credit}{" "}
            <a
              href="https://ddinter.scbdd.com"
              target="_blank"
              rel="noopener noreferrer"
              className="underline underline-offset-2"
            >
              DDInter
            </a>{" "}
            (CC BY-NC-SA 4.0).
          </p>
        </>
      )}
    </div>
  );
}
