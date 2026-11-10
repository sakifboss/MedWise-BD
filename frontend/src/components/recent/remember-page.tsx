"use client";

import { useEffect } from "react";

import { rememberPage, type RecentItem } from "@/lib/recent";

/** Adds this ranking or alternatives page to "Recently viewed" on this device. Renders nothing. */
export function RememberPage({ item }: { item: Omit<RecentItem, "viewedOn"> }) {
  const { kind, name, genericName, strength, dosageForm, href } = item;
  useEffect(() => {
    rememberPage({ kind, name, genericName, strength, dosageForm, href });
  }, [kind, name, genericName, strength, dosageForm, href]);
  return null;
}
