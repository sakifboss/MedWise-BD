"use client";

import { Loader2 } from "lucide-react";
import { useState } from "react";

import { ConfirmStep } from "@/components/prescription/confirm-step";
import { ResultsStep } from "@/components/prescription/results-step";
import { NONE, optionKey, type DraftItem } from "@/components/prescription/types";
import { UploadStep } from "@/components/prescription/upload-step";
import { useDict } from "@/i18n/client";
import { api, ApiError, type MatchOption, type PrescriptionItem } from "@/lib/api";
import { prepareImage } from "@/lib/image";

type Step =
  | { kind: "upload"; error: string | null }
  | { kind: "reading" }
  | { kind: "confirm" }
  | { kind: "results"; selections: MatchOption[] };

function toDraft(item: PrescriptionItem, index: number): DraftItem {
  return {
    key: `rx-${index}`,
    extractedName: item.extracted_name,
    extractedStrength: item.extracted_strength,
    options: item.options,
    choice: item.suggested_index != null ? String(item.suggested_index) : NONE,
  };
}

function selectedOptions(items: DraftItem[]): MatchOption[] {
  const seen = new Set<string>();
  const result: MatchOption[] = [];
  for (const item of items) {
    const option = item.choice === NONE ? undefined : item.options[Number(item.choice)];
    if (option && !seen.has(optionKey(option))) {
      seen.add(optionKey(option));
      result.push(option);
    }
  }
  return result;
}

export function PrescriptionFlow() {
  const t = useDict();
  const [step, setStepState] = useState<Step>({ kind: "upload", error: null });
  const [items, setItems] = useState<DraftItem[]>([]);

  function setStep(next: Step) {
    setStepState(next);
    window.scrollTo({ top: 0 });
  }

  async function readPhoto(file: File) {
    setStep({ kind: "reading" });
    try {
      const { blob, filename } = await prepareImage(file);
      const response = await api.readPrescription(blob, filename);
      setItems(response.items.map(toDraft));
      setStep({ kind: "confirm" });
    } catch (error) {
      const message =
        error instanceof ApiError
          ? (t.prescription.errors[error.code] ?? error.message)
          : t.prescription.unknownError;
      setStep({ kind: "upload", error: message });
    }
  }

  function restart() {
    setItems([]);
    setStep({ kind: "upload", error: null });
  }

  switch (step.kind) {
    case "upload":
      return <UploadStep onFile={readPhoto} error={step.error} />;
    case "reading":
      return (
        <div role="status" className="flex flex-col items-center gap-3 py-16 text-center">
          <Loader2 aria-hidden className="size-8 animate-spin text-primary" />
          <p className="font-medium">{t.prescription.reading}</p>
          <p className="text-sm text-muted-foreground">{t.prescription.readingTime}</p>
        </div>
      );
    case "confirm":
      return (
        <ConfirmStep
          items={items}
          onItemsChange={setItems}
          onConfirm={() => setStep({ kind: "results", selections: selectedOptions(items) })}
          onRestart={restart}
        />
      );
    case "results":
      return (
        <ResultsStep
          selections={step.selections}
          onBack={() => setStep({ kind: "confirm" })}
          onRestart={restart}
        />
      );
  }
}
