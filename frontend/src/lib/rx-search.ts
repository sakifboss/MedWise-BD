/**
 * Search pacing for the Rx Pad. Search requests carry only the typed medicine text (no cookie that
 * identifies the doctor: the session cookie is limited to /api/doctor). The pad waits for a pause
 * in typing (250 ms) and at least 2 characters, remembers answers, cancels stale requests, and
 * never sends more than 60 searches a minute from one tab: half the server's limit of 120 a minute
 * per client, so a doctor writing prescriptions all day never reaches it.
 */

export const SEARCH_DEBOUNCE_MS = 250;
export const SEARCH_MIN_CHARS = 2;
export const SEARCH_PER_MINUTE = 60;
export const RETRY_AFTER_429_MS = 5000;

export function searchKey(text: string): string | null {
  const key = text.trim().replace(/\s+/g, " ").toLowerCase();
  return key.length >= SEARCH_MIN_CHARS ? key : null;
}

/** At most `limit` requests in any `windowMs`; delay() says how long to wait before the next. */
export class SearchPacer {
  private sent: number[] = [];

  constructor(
    private readonly limit = SEARCH_PER_MINUTE,
    private readonly windowMs = 60_000,
    private readonly now: () => number = Date.now,
  ) {}

  private trim(at: number) {
    while (this.sent.length && this.sent[0] <= at - this.windowMs) this.sent.shift();
  }

  delay(): number {
    const at = this.now();
    this.trim(at);
    return this.sent.length < this.limit ? 0 : this.sent[0] + this.windowMs - at;
  }

  record(): void {
    const at = this.now();
    this.trim(at);
    this.sent.push(at);
  }
}

/** Answers by search key, newest kept (at most `size`). */
export class SearchCache<T> {
  private map = new Map<string, T>();

  constructor(private readonly size = 200) {}

  get(key: string): T | undefined {
    const value = this.map.get(key);
    if (value !== undefined) {
      this.map.delete(key);
      this.map.set(key, value);
    }
    return value;
  }

  set(key: string, value: T): void {
    this.map.delete(key);
    this.map.set(key, value);
    while (this.map.size > this.size) this.map.delete(this.map.keys().next().value as string);
  }
}
