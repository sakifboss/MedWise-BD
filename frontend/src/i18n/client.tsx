"use client";

import { createContext, useContext } from "react";

import { DEFAULT_LANG, DICTIONARIES, type Dict, type Lang } from "@/i18n/dictionaries";

const LangContext = createContext<Lang>(DEFAULT_LANG);

/** Set once in the root layout from the cookie, so client components render in the same language. */
export function LangProvider({ lang, children }: { lang: Lang; children: React.ReactNode }) {
  return <LangContext.Provider value={lang}>{children}</LangContext.Provider>;
}

export function useDict(): Dict {
  return DICTIONARIES[useContext(LangContext)];
}
