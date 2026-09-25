import { Badge } from "@/components/ui/badge";
import type { Severity } from "@/lib/api";
import { capitalize } from "@/lib/format";
import { cn } from "@/lib/utils";

const STYLES: Record<Severity, string> = {
  major: "border-red-300 bg-red-50 text-red-800",
  moderate: "border-amber-300 bg-amber-50 text-amber-900",
  minor: "border-slate-300 bg-slate-50 text-slate-700",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <Badge variant="outline" className={cn(STYLES[severity])}>
      {capitalize(severity)}
    </Badge>
  );
}
