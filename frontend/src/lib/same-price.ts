/** Prices are compared in whole poisha, so 1.2 and 1.2000001 count as the same price. */
function poisha(price: number): number {
  return Math.round(price * 100);
}

/**
 * The shared price per unit when a compared group has more than one brand and every brand costs
 * the same; otherwise null (mixed prices, a single brand, or no brands).
 */
export function samePrice(items: readonly { price_per_unit: number }[]): number | null {
  if (items.length < 2) return null;
  const first = poisha(items[0].price_per_unit);
  return items.every((item) => poisha(item.price_per_unit) === first) ? items[0].price_per_unit : null;
}
