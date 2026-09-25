"use client";

import { Loader2 } from "lucide-react";
import { useState } from "react";

import { ConfirmStep } from "@/components/prescription/confirm-step";
import { ResultsStep } from "@/components/prescription/results-step";
import { NONE, optionKey, type DraftItem } from "@/components/prescription/types";
import { UploadStep } from "@/components/prescription/upload-step";
import { api, ApiError, type MatchOption, type PrescriptionItem } from "@/lib/api";
import { prepareImage } from "@/lib/image";

type Step =
  | { kind: "upload"; error: string | null }
  | { kind: "reading" }
  | { kind: "confirm" }
  | { kind: "results"; selections: MatchOption[] };

const ERROR_MESSAGES: Record<string, string> = {
  unsupported_file: "That file isn’t a supported image. Please upload a JPEG, PNG, WebP or HEIC photo.",
  file_too_large: "That photo is too large. Please try a smaller photo.",
  ocr_busy: "Many prescriptions are being read right now. Please try again in a minute.",
  ocr_unavailable: "Prescription reading is unavailable right now. You can still search by name.",
  ocr_failed: "We couldn’t read that photo. Try a clearer, well-lit photo of the prescription.",
};

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
          ? (ERROR_MESSAGES[error.code] ?? error.message)
          : "Something went wrong. Please try again.";
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
          <p className="font-medium">Reading your prescription…</p>
          <p className="text-sm text-muted-foreground">This usually takes 5–15 seconds.</p>
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
