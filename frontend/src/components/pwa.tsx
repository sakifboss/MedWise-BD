"use client";

import { Download } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { useDict } from "@/i18n/client";

/** Registers the offline-page service worker (production only, so local dev never serves stale code). */
export function ServiceWorkerRegistration() {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production" || !("serviceWorker" in navigator)) return;
    navigator.serviceWorker.register("/sw.js").catch(() => {
      // Not critical: the site works the same without it.
    });
  }, []);
  return null;
}

type InstallPromptEvent = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: string }> };

/**
 * "Install app" button. Shown only when the browser offers installation (Chrome, Edge, Samsung
 * Internet on Android) and the app is not already installed.
 */
export function InstallAppButton() {
  const t = useDict();
  const [prompt, setPrompt] = useState<InstallPromptEvent | null>(null);

  useEffect(() => {
    function onPrompt(event: Event) {
      event.preventDefault(); // keep the browser's own banner from popping up; we offer a button instead
      setPrompt(event as InstallPromptEvent);
    }
    function onInstalled() {
      setPrompt(null);
    }
    window.addEventListener("beforeinstallprompt", onPrompt);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onPrompt);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  if (!prompt) return null;

  async function install() {
    if (!prompt) return;
    await prompt.prompt();
    await prompt.userChoice;
    setPrompt(null); // the event can only be used once
  }

  return (
    <Button type="button" variant="outline" size="sm" onClick={install} className="print:hidden">
      <Download aria-hidden />
      {t.pwa.install}
    </Button>
  );
}
