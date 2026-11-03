"use client";

import { useSearchParams } from "next/navigation";
import { createContext, useCallback, useContext, useMemo, useState } from "react";

import { parseQuantity, quantityUnit, type QuantityUnit } from "@/lib/savings";

export const QUANTITY_PARAM = "per";

type SavingsState = {
  unit: QuantityUnit;
  quantity: number | null;
  setQuantity: (value: number | null) => void;
  /** Price per unit of the user's own medicine, if this page has one selected. */
  selectedPrice: number | null;
};

const SavingsContext = createContext<SavingsState | null>(null);

/** Keeps the quantity in the URL (?per=2) so a shared link shows the same costs. */
function writeQuantityToUrl(value: number | null): void {
  const url = new URL(window.location.href);
  if (value === null) url.searchParams.delete(QUANTITY_PARAM);
  else url.searchParams.set(QUANTITY_PARAM, String(value));
  window.history.replaceState(null, "", url);
}

export function SavingsProvider({
  dosageForm,
  selectedPrice,
  children,
}: {
  dosageForm: string;
  selectedPrice: number | null;
  children: React.ReactNode;
}) {
  const searchParams = useSearchParams();
  const unit = useMemo(() => quantityUnit(dosageForm), [dosageForm]);
  const [quantity, setQuantityState] = useState<number | null>(() =>
    parseQuantity(searchParams.get(QUANTITY_PARAM), unit),
  );

  const setQuantity = useCallback((value: number | null) => {
    setQuantityState(value);
    writeQuantityToUrl(value);
  }, []);

  const value = useMemo(
    () => ({ unit, quantity, setQuantity, selectedPrice }),
    [unit, quantity, setQuantity, selectedPrice],
  );
  return <SavingsContext.Provider value={value}>{children}</SavingsContext.Provider>;
}

export function useSavings(): SavingsState {
  const state = useContext(SavingsContext);
  if (!state) throw new Error("useSavings must be used inside SavingsProvider");
  return state;
}
