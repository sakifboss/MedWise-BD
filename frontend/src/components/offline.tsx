"use client";

import { CloudDownload, Loader2, WifiOff } from "lucide-react";
import { useEffect, useState, useSyncExternalStore } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useDict } from "@/i18n/client";
import { api } from "@/lib/api";
import {
  canSaveForOffline,
  offlineUrls,
  parseSavedAt,
  saveForOffline,
  savedAtOfThisPage,
  savedMedicines,
  type SavedMedicine,
} from "@/lib/offline";

// The saved-at <meta> is put in by the service worker and never changes while the page is open.
const noSubscription = () => () => {};

/** On a page served from the offline copy: says when it was saved and that prices may differ. */
export function OfflineBanner() {
  const t = useDict();
  const value = useSyncExternalStore(noSubscription, savedAtOfThisPage, () => null);
  const savedAt = parseSavedAt(value);

  if (!savedAt) return null;
  return (
    <Alert
      className="mb-6 border-amber-300 bg-amber-50 text-amber-950 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100"
      data-testid="offline-banner"
      role="status"
    >
      <WifiOff aria-hidden />
      <AlertDescription className="text-amber-950 dark:text-amber-100">{t.offline.banner(t.fmt.date(savedAt))}</AlertDescription>
    </Alert>
  );
}

type SaveState =
  | { status: "idle" }
  | { status: "saving"; done: number; total: number }
  | { status: "done"; saved: number; failed: number }
  | { status: "failed" }
  | { status: "unsupported" };

/** "Save all medicines for offline use": every generic page and every ranking page. */
export function SaveForOffline() {
  const t = useDict();
  const o = t.offline;
  const [state, setState] = useState<SaveState>({ status: "idle" });

  async function save() {
    if (!canSaveForOffline()) {
      setState({ status: "unsupported" });
      return;
    }
    setState({ status: "saving", done: 0, total: 0 });
    try {
      const urls = offlineUrls(await api.generics());
      setState({ status: "saving", done: 0, total: urls.length });
      const result = await saveForOffline(urls, ({ done, total }) => setState({ status: "saving", done, total }));
      setState(result.saved === 0 ? { status: "failed" } : { status: "done", ...result });
    } catch {
      setState({ status: "failed" });
    }
  }

  const saving = state.status === "saving";
  return (
    <div className="space-y-1" data-testid="save-offline">
      <Button variant="outline" size="sm" onClick={save} disabled={saving} className="h-auto min-h-7 py-1 text-left whitespace-normal">
        {saving ? <Loader2 aria-hidden className="animate-spin" /> : <CloudDownload aria-hidden />}
        {o.saveAll}
      </Button>
      <p aria-live="polite">
        {state.status === "saving" &&
          state.total > 0 &&
          o.saving(t.fmt.int(state.done), t.fmt.int(state.total))}
        {state.status === "done" &&
          (state.failed === 0
            ? o.saved(t.fmt.int(state.saved))
            : o.partly(t.fmt.int(state.saved), t.fmt.int(state.failed)))}
        {state.status === "failed" && o.failed}
        {state.status === "unsupported" && o.unsupported}
      </p>
      <p>{o.languageNote}</p>
    </div>
  );
}

/** When search cannot reach the server: say it needs internet and list the saved medicines. */
export function OfflineSearchHelp() {
  const t = useDict();
  const [saved, setSaved] = useState<SavedMedicine[] | null>(null);

  useEffect(() => {
    let active = true;
    savedMedicines().then((list) => active && setSaved(list));
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="space-y-2" data-testid="offline-search">
      <p className="font-medium text-foreground">{t.offline.searchOffline}</p>
      {saved !== null &&
        (saved.length === 0 ? (
          <p>{t.offline.noneSaved}</p>
        ) : (
          <>
            <p>{t.offline.savedList}</p>
            <ul className="flex flex-wrap gap-2">
              {saved.map((m) => (
                <li key={m.id}>
                  {/* A full page load (not client navigation), so the saved copy is served offline. */}
                  <a
                    href={m.href}
                    className="inline-block rounded-full border px-3 py-1 text-foreground hover:bg-muted"
                  >
                    {m.name}
                  </a>
                </li>
              ))}
            </ul>
          </>
        ))}
    </div>
  );
}
