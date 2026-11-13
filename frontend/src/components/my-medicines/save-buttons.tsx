"use client";

import { BookmarkCheck, BookmarkPlus } from "lucide-react";
import { useState } from "react";

import { useMyMedicines } from "@/components/my-medicines/use-my-medicines";
import { useSavingsIfAny } from "@/components/savings/savings-context";
import { Button } from "@/components/ui/button";
import { useDict } from "@/i18n/client";
import type { AlternativesResponse, MatchOption, RankedAlternative } from "@/lib/api";
import { fromRanking, today, upsert, type SavedMedicine } from "@/lib/my-medicines";

/** "Save to My Medicines" for one brand of a ranking page (keeps the calculator's amount, if any). */
export function SaveToMyMedicines({
  data,
  brand,
}: {
  data: Pick<AlternativesResponse, "generic" | "strength" | "dosage_form">;
  brand: Pick<RankedAlternative, "code" | "name">;
}) {
  const t = useDict();
  const { list, available, change } = useMyMedicines();
  const savings = useSavingsIfAny();
  const [failed, setFailed] = useState(false);
  const saved = list.items.some((m) => m.brandCode === brand.code);

  if (!available) return null;
  return (
    <div className="print:hidden">
      <Button
        variant={saved ? "secondary" : "outline"}
        size="sm"
        onClick={() => setFailed(!change((l) => upsert(l, fromRanking(data, brand, savings?.quantity ?? null))))}
        aria-pressed={saved}
      >
        {saved ? <BookmarkCheck aria-hidden /> : <BookmarkPlus aria-hidden />}
        {saved ? t.myMeds.saved : t.myMeds.save}
      </Button>
      {failed && <p className="mt-1 text-xs text-destructive">{t.myMeds.unavailable}</p>}
    </div>
  );
}

function fromOption(option: MatchOption, unitsPerDay: number | null): SavedMedicine | null {
  if (option.kind !== "brand" || !option.brand_code) return null; // a generic without a brand
  return {
    brandCode: option.brand_code,
    brandName: option.name,
    genericName: option.generic_name,
    strength: option.strength,
    dosageForm: option.dosage_form,
    unitsPerDay,
    reminderTimes: [],
    addedOn: today(),
  };
}

/** "Save all to My Medicines" on prescription results: every confirmed brand, with its amount. */
export function SaveAllToMyMedicines({ rows }: { rows: { option: MatchOption; quantity: number | null }[] }) {
  const t = useDict();
  const { available, change } = useMyMedicines();
  const [message, setMessage] = useState<string | null>(null);

  if (!available) return null;
  function saveAll() {
    const items = rows.map((r) => fromOption(r.option, r.quantity)).filter((m): m is SavedMedicine => m !== null);
    const ok = change((l) => items.reduce(upsert, l));
    if (!ok) {
      setMessage(t.myMeds.unavailable);
      return;
    }
    const skipped = rows.length - items.length;
    setMessage(
      [t.myMeds.savedAll(t.fmt.int(items.length)), skipped > 0 ? t.myMeds.skipped(t.fmt.int(skipped)) : ""]
        .filter(Boolean)
        .join(" "),
    );
  }

  return (
    <div className="space-y-1 print:hidden">
      <Button variant="outline" onClick={saveAll}>
        <BookmarkPlus aria-hidden />
        {t.myMeds.saveAll}
      </Button>
      <p aria-live="polite" className="text-sm text-muted-foreground">
        {message}
      </p>
    </div>
  );
}
