import "server-only";

import { cookies } from "next/headers";

import { DEFAULT_LANG, DICTIONARIES, isLang, LANG_COOKIE, type Dict, type Lang } from "@/i18n/dictionaries";
import { DEFAULT_TEXT_SIZE, isTextSize, TEXT_SIZE_COOKIE, type TextSize } from "@/lib/text-size";
import { DEFAULT_THEME, isTheme, THEME_COOKIE, type Theme } from "@/lib/theme";

/** The visitor's language, from the cookie set by the language toggle. */
export async function getLang(): Promise<Lang> {
  const value = (await cookies()).get(LANG_COOKIE)?.value;
  return isLang(value) ? value : DEFAULT_LANG;
}

export async function getDict(): Promise<Dict> {
  return DICTIONARIES[await getLang()];
}

/** The visitor's theme, from the cookie set by the display menu. */
export async function getTheme(): Promise<Theme> {
  const value = (await cookies()).get(THEME_COOKIE)?.value;
  return isTheme(value) ? value : DEFAULT_THEME;
}

/** The visitor's text size, from the cookie set by the display menu. */
export async function getTextSize(): Promise<TextSize> {
  const value = (await cookies()).get(TEXT_SIZE_COOKIE)?.value;
  return isTextSize(value) ? value : DEFAULT_TEXT_SIZE;
}
