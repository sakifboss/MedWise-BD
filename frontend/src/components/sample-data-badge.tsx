import { Badge } from "@/components/ui/badge";

export const SAMPLE_DATA_NOTE =
  "Brand names, prices and medicine details are sample data, not official DGDA data.";

export function SampleDataBadge() {
  return (
    <Badge
      variant="outline"
      title={SAMPLE_DATA_NOTE}
      className="border-amber-300 bg-amber-50 text-amber-900"
    >
      Sample data
    </Badge>
  );
}
