"use client";

import { Camera, ImageUp, ShieldCheck } from "lucide-react";
import { useId } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function UploadStep({
  onFile,
  error,
}: {
  onFile: (file: File) => void;
  error: string | null;
}) {
  const inputId = useId();

  return (
    <div className="space-y-5">
      <label
        htmlFor={inputId}
        className="flex cursor-pointer flex-col items-center gap-3 rounded-xl border-2 border-dashed bg-muted/30 px-4 py-10 text-center transition-colors hover:bg-muted/50 focus-within:border-primary"
      >
        <span className="flex size-12 items-center justify-center rounded-full bg-primary/10 text-primary">
          <Camera aria-hidden className="size-6" />
        </span>
        <span className="font-medium">Take or choose a photo of the prescription</span>
        <span className="text-sm text-muted-foreground">JPEG, PNG, WebP or HEIC</span>
        <input
          id={inputId}
          type="file"
          accept="image/*"
          capture="environment"
          className="sr-only"
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = "";
            if (file) onFile(file);
          }}
        />
        <span aria-hidden className={cn(buttonVariants({ variant: "outline" }), "mt-1")}>
          <ImageUp />
          Choose photo
        </span>
      </label>

      {error && (
        <Alert variant="destructive" role="alert">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="flex gap-3 rounded-xl border p-4 text-sm">
        <ShieldCheck aria-hidden className="mt-0.5 size-5 shrink-0 text-primary" />
        <div className="space-y-2 text-muted-foreground">
          <p>
            <strong className="font-medium text-foreground">Only medicine names and strengths are read.</strong>{" "}
            We never generate doses or medical advice, and you confirm every medicine before seeing
            results.
          </p>
          <p>
            Your photo is sent to Google Gemini to read the text and is not stored by MedWise. Google
            may use images sent through its free API tier to improve its services, so avoid photos
            showing details you don’t want shared.
          </p>
        </div>
      </div>
    </div>
  );
}
