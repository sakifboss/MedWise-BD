import "server-only";

import { cookies } from "next/headers";

import { DEFAULT_LANG, DICTIONARIES, isLang, LANG_COOKIE, type Dict, type Lang } from "@/i18n/dictionaries";

/** The visitor's language, from the cookie set by the language toggle. */
export async function getLang(): Promise<Lang> {
  const value = (await cookies()).get(LANG_COOKIE)?.value;
  return isLang(value) ? value : DEFAULT_LANG;
}

export async function getDict(): Promise<Dict> {
  return DICTIONARIES[await getLang()];
}
