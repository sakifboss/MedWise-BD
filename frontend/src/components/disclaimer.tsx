"use client";

import { Stethoscope } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { useDict } from "@/i18n/client";

export function Disclaimer() {
  const t = useDict();
  return (
    <Alert className="border-primary/30 bg-primary/5">
      <Stethoscope aria-hidden />
      <AlertDescription className="font-medium text-foreground">{t.disclaimer}</AlertDescription>
    </Alert>
  );
}
