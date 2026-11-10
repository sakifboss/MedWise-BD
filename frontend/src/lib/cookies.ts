/** Small display preferences (theme, text size) kept in cookies so the server can render them. */
const ONE_YEAR = 60 * 60 * 24 * 365;

/** A cookie's value from a Cookie header or document.cookie string, or null. */
export function readCookie(cookies: string, name: string): string | null {
  for (const part of cookies.split(";")) {
    const [key, ...rest] = part.trim().split("=");
    if (key === name) return rest.join("=");
  }
  return null;
}

/** A long-lived, site-wide cookie. */
export function preferenceCookie(name: string, value: string): string {
  return `${name}=${value}; path=/; max-age=${ONE_YEAR}; samesite=lax`;
}
