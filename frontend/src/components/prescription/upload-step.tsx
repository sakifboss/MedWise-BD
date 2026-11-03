"use client";

import { Camera, ImageUp, ShieldCheck } from "lucide-react";
import { useId } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { buttonVariants } from "@/components/ui/button";
import { useDict } from "@/i18n/client";
import { cn } from "@/lib/utils";

export function UploadStep({
  onFile,
  error,
}: {
  onFile: (file: File) => void;
  error: string | null;
}) {
  const inputId = useId();
  const { upload } = useDict().prescription;

  return (
    <div className="space-y-5">
      <label
        htmlFor={inputId}
        className="flex cursor-pointer flex-col items-center gap-3 rounded-xl border-2 border-dashed bg-muted/30 px-4 py-10 text-center transition-colors hover:bg-muted/50 focus-within:border-primary"
      >
        <span className="flex size-12 items-center justify-center rounded-full bg-primary/10 text-primary">
          <Camera aria-hidden className="size-6" />
        </span>
        <span className="font-medium">{upload.prompt}</span>
        <span className="text-sm text-muted-foreground">{upload.formats}</span>
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
          {upload.choose}
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
            <strong className="font-medium text-foreground">{upload.readOnly}</strong> {upload.readOnlyMore}
          </p>
          <p>{upload.privacy}</p>
        </div>
      </div>
    </div>
  );
}
