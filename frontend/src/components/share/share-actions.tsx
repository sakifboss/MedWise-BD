"use client";

import { Check, MessageCircle, Printer, Share2 } from "lucide-react";
import { useState, useSyncExternalStore } from "react";

import { QrCode } from "@/components/share/qr-code";
import { Button } from "@/components/ui/button";
import { useDict } from "@/i18n/client";

function absolute(url: string | undefined): string {
  return new URL(url ?? window.location.href, window.location.origin).toString();
}

/**
 * Share, WhatsApp and print buttons for a page, plus a QR code and link that only appear on paper.
 * `url` defaults to the current page; `text` is the message (without the link).
 */
export function ShareActions({ title, text, url }: { title: string; text: string; url?: string }) {
  const t = useDict();
  const [copied, setCopied] = useState(false);

  async function share() {
    const link = absolute(url);
    if (typeof navigator.share === "function") {
      try {
        await navigator.share({ title, text, url: link });
        return;
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return; // user closed the sheet
      }
    }
    await navigator.clipboard.writeText(`${text}\n${link}`);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2500);
  }

  function whatsapp() {
    const message = `${text}\n${absolute(url)}`;
    window.open(`https://wa.me/?text=${encodeURIComponent(message)}`, "_blank", "noopener,noreferrer");
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2 print:hidden">
        <Button type="button" variant="outline" size="sm" onClick={share}>
          {copied ? <Check aria-hidden /> : <Share2 aria-hidden />}
          {copied ? t.share.copied : t.share.share}
        </Button>
        <Button type="button" variant="outline" size="sm" onClick={whatsapp}>
          <MessageCircle aria-hidden />
          {t.share.whatsapp}
        </Button>
        <Button type="button" variant="outline" size="sm" onClick={() => window.print()}>
          <Printer aria-hidden />
          {t.share.print}
        </Button>
        <span aria-live="polite" className="sr-only">
          {copied ? t.share.copied : ""}
        </span>
      </div>
      <div className="hidden items-center gap-4 rounded-lg border p-3 print:flex">
        <QrCode url={url} label={t.share.scanToOpen} />
        <div className="space-y-1 text-sm">
          <p className="font-medium">{t.share.scanToOpen}</p>
          <PrintedLink url={url} />
        </div>
      </div>
    </div>
  );
}

const noopSubscribe = () => () => {};

/** The link as text on paper, for people who cannot scan the QR code. */
function PrintedLink({ url }: { url?: string }) {
  const href = useSyncExternalStore(noopSubscribe, () => readable(absolute(url)), () => "");
  return <p className="break-all text-xs text-muted-foreground">{href}</p>;
}

/** "/share?m=b%3A22%3A2" -> "/share?m=b:22:2", easier to read and type from paper. */
function readable(link: string): string {
  try {
    return decodeURIComponent(link).replaceAll("+", " ");
  } catch {
    return link;
  }
}
