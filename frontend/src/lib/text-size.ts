/**
 * Text size (Normal / Large), chosen in the Display menu and kept in a cookie like the theme. The
 * server renders <html data-text="...">; Large raises the root font size on screen (every rem-based
 * size grows: text, buttons, icons), and print stays normal.
 */
import { preferenceCookie, readCookie } from "./cookies";

export const TEXT_SIZES = ["normal", "large"] as const;
export type TextSize = (typeof TEXT_SIZES)[number];
export const DEFAULT_TEXT_SIZE: TextSize = "normal";
export const TEXT_SIZE_COOKIE = "text";

export function isTextSize(value: unknown): value is TextSize {
  return typeof value === "string" && (TEXT_SIZES as readonly string[]).includes(value);
}

export function textSizeCookie(size: TextSize): string {
  return preferenceCookie(TEXT_SIZE_COOKIE, size);
}

export function textSizeFromCookies(cookies: string): TextSize {
  const value = readCookie(cookies, TEXT_SIZE_COOKIE);
  return isTextSize(value) ? value : DEFAULT_TEXT_SIZE;
}

// ---------------------------------------------------------------- browser only

const CHANGED = "medwise:text-size";

export function pageTextSize(): TextSize {
  const value = document.documentElement.dataset.text;
  return isTextSize(value) ? value : DEFAULT_TEXT_SIZE;
}

export function applyTextSize(size: TextSize, remember = true): void {
  if (remember) document.cookie = textSizeCookie(size);
  document.documentElement.dataset.text = size;
  window.dispatchEvent(new Event(CHANGED));
}

/** A page saved for offline use keeps the size it was saved with; follow the cookie instead. */
export function syncTextSizeWithCookie(): void {
  const saved = textSizeFromCookies(document.cookie);
  if (saved !== pageTextSize()) applyTextSize(saved, false);
}

export function subscribeTextSize(onChange: () => void): () => void {
  window.addEventListener(CHANGED, onChange);
  return () => window.removeEventListener(CHANGED, onChange);
}
