/**
 * The doctor's own Rx Pad preferences on this device (localStorage), never anything about a patient.
 * Today: the language of the patient instructions on the print. Versioned; every read and write is
 * in try/catch, so the pad works (with the default) when storage is blocked.
 */

export const RX_PREFS_KEY = "medwise.rxPrefs";
const VERSION = 1;

export const PRINT_LANGUAGES = ["bn", "both", "en"] as const;
export type PrintLanguage = (typeof PRINT_LANGUAGES)[number];
/** For a device that has no saved choice yet. */
export const DEFAULT_PRINT_LANGUAGE: PrintLanguage = "bn";

export function parsePrintLanguage(raw: string | null): PrintLanguage {
  try {
    const data = raw ? (JSON.parse(raw) as { v?: unknown; printLanguage?: unknown }) : null;
    const value = data?.v === VERSION ? data.printLanguage : null;
    return PRINT_LANGUAGES.includes(value as PrintLanguage) ? (value as PrintLanguage) : DEFAULT_PRINT_LANGUAGE;
  } catch {
    return DEFAULT_PRINT_LANGUAGE;
  }
}

export function loadPrintLanguage(): PrintLanguage {
  try {
    return parsePrintLanguage(window.localStorage.getItem(RX_PREFS_KEY));
  } catch {
    return DEFAULT_PRINT_LANGUAGE;
  }
}

export function savePrintLanguage(language: PrintLanguage): void {
  try {
    window.localStorage.setItem(RX_PREFS_KEY, JSON.stringify({ v: VERSION, printLanguage: language }));
  } catch {
    // Storage blocked or full: the choice simply is not remembered.
  }
}
