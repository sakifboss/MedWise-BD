/**
 * Text for the printed page's margins (CSS @page margin boxes can only show CSS values): the
 * doctor's name at the top of page 2 onwards, and the MedWise BD footer on every page. Set as
 * custom properties on <html> while the Rx Pad is open; removed when it closes.
 */
export function setPrintMargins(runningHead: string, footer: string): () => void {
  const root = document.documentElement;
  root.style.setProperty("--rx-running-head", JSON.stringify(runningHead));
  root.style.setProperty("--rx-footer", JSON.stringify(footer));
  return () => {
    root.style.removeProperty("--rx-running-head");
    root.style.removeProperty("--rx-footer");
  };
}

/** Asks before leaving the page while the prescription has content (nothing is saved anywhere). */
export function confirmBeforeLeaving(hasContent: () => boolean): () => void {
  const handler = (event: BeforeUnloadEvent) => {
    if (!hasContent()) return;
    event.preventDefault();
    event.returnValue = "";
  };
  window.addEventListener("beforeunload", handler);
  return () => window.removeEventListener("beforeunload", handler);
}

/** Today in the device's time zone, as YYYY-MM-DD (for the date field). */
export function todayIso(): string {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60_000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}
