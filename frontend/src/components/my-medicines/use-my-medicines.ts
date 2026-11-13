"use client";

import { useCallback, useEffect, useMemo, useSyncExternalStore } from "react";

import { api } from "@/lib/api";

import {
  loadList,
  migrate,
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
  const migrating = Boolean(list.legacy?.length);

  // A list saved before brand codes existed: match it to codes once, with the public brand index.
  useEffect(() => {
    if (!migrating) return;
    let active = true;
    api.brandIndex().then(
      (index) => active && saveList(migrate(loadList(), index.brands)),
      () => undefined, // offline: keep the old list untouched and try again next time
    );
    return () => {
      active = false;
    };
  }, [migrating]);

  /** Apply a change to the latest stored list; false when the browser does not allow saving. */
  const change = useCallback((fn: (list: MyMedicinesList) => MyMedicinesList) => saveList(fn(loadList())), []);

  return { list, available, change, migrating };
}
