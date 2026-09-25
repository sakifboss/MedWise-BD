import { SAMPLE_DATA_NOTE } from "@/components/sample-data-badge";

export function SiteFooter() {
  return (
    <footer className="border-t">
      <div className="mx-auto w-full max-w-3xl space-y-1 px-4 py-6 text-xs text-muted-foreground">
        <p>
          MedWise BD compares medicines using its own database. It does not give medical advice.
        </p>
        <p>{SAMPLE_DATA_NOTE}</p>
      </div>
    </footer>
  );
}
