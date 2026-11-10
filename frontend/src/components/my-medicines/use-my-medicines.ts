"use client";

import { useCallback, useMemo, useSyncExternalStore } from "react";

import {
  loadList,
  parseListText,
  saveList,
  snapshot,
  storageAvailable,
  subscribe,
  type MyMedicinesList,
} from "@/lib/my-medicines";

const noSubscription = () => () => {};

/** The list saved on this device, shared by every component on the page (and other tabs). */
export function useMyMedicines() {
  const text = useSyncExternalStore(subscribe, snapshot, () => "");
  const available = useSyncExternalStore(noSubscription, storageAvailable, () => true);
  const list = useMemo(() => parseListText(text || null), [text]);

  /** Apply a change to the latest stored list; false when the browser does not allow saving. */
  const change = useCallback((fn: (list: MyMedicinesList) => MyMedicinesList) => saveList(fn(loadList())), []);

  return { list, available, change };
}
