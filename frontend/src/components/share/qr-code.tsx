"use client";

import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";

function absolute(url: string | undefined): string {
  return new URL(url ?? window.location.href, window.location.origin).toString();
}

/**
 * QR code for a link (default: the current page, including its ?per= quantity). It is rebuilt
 * just before printing, because the calculator can change the URL after the page loads.
 */
export function QrCode({ url, label, className }: { url?: string; label: string; className?: string }) {
  const [svg, setSvg] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function render() {
      const QRCode = (await import("qrcode")).default;
      const markup = await QRCode.toString(absolute(url), { type: "svg", margin: 1, errorCorrectionLevel: "M" });
      if (!cancelled) setSvg(markup);
    }
    void render();
    window.addEventListener("beforeprint", render);
    return () => {
      cancelled = true;
      window.removeEventListener("beforeprint", render);
    };
  }, [url]);

  if (!svg) return null;
  return (
    <div
      role="img"
      aria-label={label}
      className={cn("size-28 [&>svg]:size-full", className)}
      // The SVG comes from the qrcode library for a URL we built, not from user HTML.
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}
