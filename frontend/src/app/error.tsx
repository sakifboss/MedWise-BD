"use client";

import { useEffect } from "react";

import { Button } from "@/components/ui/button";
import { useDict } from "@/i18n/client";

export default function ErrorPage({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  const t = useDict();
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="space-y-4 py-10 text-center">
      <h1 className="text-xl font-semibold">{t.errorPage.title}</h1>
      <p className="text-muted-foreground">{t.errorPage.text}</p>
      <Button onClick={() => retry()}>{t.errorPage.retry}</Button>
    </div>
  );
}
