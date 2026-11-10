/**
 * Light / dark theme, chosen by the visitor and kept in a cookie (like the language). The server
 * renders <html data-theme="..."> from it, so there is no flash and no inline script (the nonce CSP
 * is unchanged). "system" follows the phone's setting through CSS (prefers-color-scheme).
 */
export const THEMES = ["system", "light", "dark"] as const;
export type Theme = (typeof THEMES)[number];
export const DEFAULT_THEME: Theme = "system";
export const THEME_COOKIE = "theme";

const ONE_YEAR = 60 * 60 * 24 * 365;

/** Browser address-bar colour per theme (the manifest keeps the brand colour). */
export const THEME_COLORS = { light: "#007565", dark: "#0f1a19" } as const;

export function isTheme(value: unknown): value is Theme {
  return typeof value === "string" && (THEMES as readonly string[]).includes(value);
}

export function themeCookie(theme: Theme): string {
  return `${THEME_COOKIE}=${theme}; path=/; max-age=${ONE_YEAR}; samesite=lax`;
}

/** The theme in a Cookie header or document.cookie string; the default when missing or invalid. */
export function themeFromCookies(cookies: string): Theme {
  for (const part of cookies.split(";")) {
    const [name, ...rest] = part.trim().split("=");
    if (name === THEME_COOKIE) {
      const value = rest.join("=");
      return isTheme(value) ? value : DEFAULT_THEME;
    }
  }
  return DEFAULT_THEME;
}

/** <meta name="theme-color"> values: one colour, or both with media queries for "system". */
export function themeColorFor(theme: Theme): { color: string; media?: string }[] {
  if (theme === "light") return [{ color: THEME_COLORS.light }];
  if (theme === "dark") return [{ color: THEME_COLORS.dark }];
  return [
    { media: "(prefers-color-scheme: light)", color: THEME_COLORS.light },
    { media: "(prefers-color-scheme: dark)", color: THEME_COLORS.dark },
  ];
}

// ---------------------------------------------------------------- browser only

const CHANGED = "medwise:theme";

/** The theme the page shows now (<html data-theme>). */
export function pageTheme(): Theme {
  const value = document.documentElement.dataset.theme;
  return isTheme(value) ? value : DEFAULT_THEME;
}

/** Show a theme now and remember it for the server. */
export function applyTheme(theme: Theme, remember = true): void {
  if (remember) document.cookie = themeCookie(theme);
  document.documentElement.dataset.theme = theme;
  window.dispatchEvent(new Event(CHANGED));
}

/** A page saved for offline use keeps the theme it was saved with; follow the cookie instead. */
export function syncThemeWithCookie(): void {
  const saved = themeFromCookies(document.cookie);
  if (saved !== pageTheme()) applyTheme(saved, false);
}

/** For useSyncExternalStore. */
export function subscribeTheme(onChange: () => void): () => void {
  window.addEventListener(CHANGED, onChange);
  return () => window.removeEventListener(CHANGED, onChange);
}
