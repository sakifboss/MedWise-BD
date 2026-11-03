const DATA_SOURCES_NOTE =
  "Data: manufacturer quality from public regulator and company sources; prices are Arogga MRPs " +
  "(Nov 2026); medicine information from the NHS website and US FDA labels; interactions from " +
  "DDInter. Not official DGDA data.";

export function SiteFooter() {
  return (
    <footer className="border-t">
      <div className="mx-auto w-full max-w-3xl space-y-1 px-4 py-6 text-xs text-muted-foreground">
        <p>
          MedWise BD compares medicines using its own database. It does not give medical advice.
        </p>
        <p>{DATA_SOURCES_NOTE}</p>
      </div>
    </footer>
  );
}
