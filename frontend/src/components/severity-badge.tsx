"use client";

import { Badge } from "@/components/ui/badge";
import { useDict } from "@/i18n/client";
import type { Severity } from "@/lib/api";
import { cn } from "@/lib/utils";

const STYLES: Record<Severity, string> = {
  major: "border-red-300 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200",
  moderate: "border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200",
  minor: "border-slate-300 bg-slate-50 text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  const t = useDict();
  return (
    <Badge variant="outline" className={cn(STYLES[severity])}>
      {t.severity[severity]}
    </Badge>
  );
}
