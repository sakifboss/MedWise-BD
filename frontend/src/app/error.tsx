"use client";

import { useEffect } from "react";

import { Button } from "@/components/ui/button";

export default function ErrorPage({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="space-y-4 py-10 text-center">
      <h1 className="text-xl font-semibold">We couldn’t load this page</h1>
      <p className="text-muted-foreground">
        The MedWise server may be starting up or temporarily unavailable. Please try again in a
        moment.
      </p>
      <Button onClick={() => retry()}>Try again</Button>
    </div>
  );
}
