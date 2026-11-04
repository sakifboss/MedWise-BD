"use client";

import { Download } from "lucide-react";
import { useEffect, useSyncExternalStore } from "react";

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

// The browser can offer installation before React has rendered the footer, so the offer is caught
// as soon as this module loads and kept here until the button reads it.
let installPrompt: InstallPromptEvent | null = null;
const listeners = new Set<() => void>();

function setInstallPrompt(value: InstallPromptEvent | null) {
  installPrompt = value;
  listeners.forEach((notify) => notify());
}

if (typeof window !== "undefined") {
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault(); // keep the browser's own banner from popping up; we offer a button instead
    setInstallPrompt(event as InstallPromptEvent);
  });
  window.addEventListener("appinstalled", () => setInstallPrompt(null));
}

function subscribe(notify: () => void) {
  listeners.add(notify);
  return () => listeners.delete(notify);
}

/**
 * "Install app" button. Shown only when the browser offers installation (Chrome, Edge, Samsung
 * Internet on Android) and the app is not already installed.
 */
export function InstallAppButton() {
  const t = useDict();
  const prompt = useSyncExternalStore(subscribe, () => installPrompt, () => null);

  if (!prompt) return null;

  async function install() {
    if (!prompt) return;
    await prompt.prompt();
    await prompt.userChoice;
    setInstallPrompt(null); // the event can only be used once
  }

  return (
    <Button type="button" variant="outline" size="sm" onClick={install} className="print:hidden">
      <Download aria-hidden />
      {t.pwa.install}
    </Button>
  );
}
