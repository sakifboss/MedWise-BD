import { Stethoscope } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";

export const DISCLAIMER = "Consult your doctor or pharmacist before changing any medicine.";

export function Disclaimer({ text = DISCLAIMER }: { text?: string }) {
  return (
    <Alert className="border-primary/30 bg-primary/5">
      <Stethoscope aria-hidden />
      <AlertDescription className="font-medium text-foreground">{text}</AlertDescription>
    </Alert>
  );
}
