import { cn } from "@/lib/utils";

/** Horizontal bar for a 0-100 value. Decorative: the number is always shown next to it. */
export function ScoreBar({ value, className }: { value: number; className?: string }) {
  const width = Math.max(0, Math.min(100, value));
  return (
    <div aria-hidden className={cn("h-2 w-full overflow-hidden rounded-full bg-muted", className)}>
      <div className="h-full rounded-full bg-primary" style={{ width: `${width}%` }} />
    </div>
  );
}
