import { describe, expect, it } from "vitest";

import { preferenceCookie, readCookie } from "./cookies";
import { DEFAULT_TEXT_SIZE, isTextSize, textSizeCookie, textSizeFromCookies } from "./text-size";

describe("cookies", () => {
  it("reads one cookie by its exact name", () => {
    expect(readCookie("lang=bn; text=large; theme=dark", "text")).toBe("large");
    expect(readCookie("context=large", "text")).toBeNull();
    expect(readCookie("", "text")).toBeNull();
    expect(readCookie("a=b=c", "a")).toBe("b=c");
  });

  it("writes long-lived, site-wide preference cookies", () => {
    expect(preferenceCookie("text", "large")).toBe("text=large; path=/; max-age=31536000; samesite=lax");
  });
});

describe("text size", () => {
  it("accepts only normal and large", () => {
    expect(isTextSize("normal") && isTextSize("large")).toBe(true);
    expect(isTextSize("huge")).toBe(false);
  });

  it("reads the cookie, with Normal when it is missing or invalid", () => {
    expect(textSizeFromCookies("theme=dark; text=large")).toBe("large");
    expect(textSizeFromCookies("text=huge")).toBe(DEFAULT_TEXT_SIZE);
    expect(textSizeFromCookies("theme=dark")).toBe("normal");
    expect(textSizeCookie("large")).toBe("text=large; path=/; max-age=31536000; samesite=lax");
  });
});
