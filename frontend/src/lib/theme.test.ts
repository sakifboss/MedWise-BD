import { describe, expect, it } from "vitest";

import { DEFAULT_THEME, isTheme, themeColorFor, themeCookie, themeFromCookies } from "./theme";

describe("theme", () => {
  it("accepts only system, light and dark", () => {
    expect(["system", "light", "dark"].every(isTheme)).toBe(true);
    expect(isTheme("blue")).toBe(false);
    expect(isTheme(undefined)).toBe(false);
  });

  it("reads the cookie, with the default when it is missing or invalid", () => {
    expect(themeFromCookies("lang=bn; theme=dark")).toBe("dark");
    expect(themeFromCookies("theme=light")).toBe("light");
    expect(themeFromCookies("lang=bn")).toBe(DEFAULT_THEME);
    expect(themeFromCookies("theme=neon; lang=en")).toBe(DEFAULT_THEME);
    expect(themeFromCookies("mytheme=dark")).toBe(DEFAULT_THEME);
  });

  it("writes a long-lived, site-wide cookie", () => {
    expect(themeCookie("dark")).toBe("theme=dark; path=/; max-age=31536000; samesite=lax");
  });

  it("gives the address bar one colour, or both for system", () => {
    expect(themeColorFor("light")).toEqual([{ color: "#007565" }]);
    expect(themeColorFor("dark")).toEqual([{ color: "#0f1a19" }]);
    expect(themeColorFor("system").map((c) => c.media)).toEqual([
      "(prefers-color-scheme: light)",
      "(prefers-color-scheme: dark)",
    ]);
  });
});
