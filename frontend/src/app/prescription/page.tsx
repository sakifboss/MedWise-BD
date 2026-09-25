import type { Metadata } from "next";

import { BackLink } from "@/components/back-link";
import { PrescriptionFlow } from "@/components/prescription/prescription-flow";

export const metadata: Metadata = {
  title: "Scan a prescription",
  description: "Read medicine names from a prescription photo and compare alternatives.",
};

export default function PrescriptionPage() {
  return (
    <div className="space-y-6">
      <BackLink href="/">Search by name instead</BackLink>
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Scan a prescription</h1>
        <p className="text-muted-foreground">
          We read the medicine names and strengths, you confirm them, then we show ranked
          alternatives for each.
        </p>
      </header>
      <PrescriptionFlow />
    </div>
  );
}
