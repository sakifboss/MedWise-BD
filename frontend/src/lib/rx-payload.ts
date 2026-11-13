/**
 * The prescription QR payload (R4), built and read only in the browser.
 *
 * Holds the medicine lines (brand code, or generic + strength + form, or a free-text name of at
 * most 40 characters; pattern, unit, food, duration, substitution) plus the issue and follow-up
 * dates. Never patient details, complaints, findings, diagnosis, allergies, tests, advice or line
 * notes. The server only ever receives SHA-256 of the canonical JSON text (to sign it); the QR
 * link puts the payload after "#", which browsers never send to any server.
 *
 * Link: https://<site>/rx#<payload>.<doctor_id>.<issued_at>.<sig>
 * <payload> = "z" + base64url(deflate-raw(JSON)) or, without CompressionStream, "p" + base64url(JSON).
 */

import { MAX_FREE_NAME, MAX_LINES, RX_UNITS, type Duration, type FoodTiming, type RxLine, type RxUnit } from "./rx";

export const PAYLOAD_VERSION = 1;
const FOODS: FoodTiming[] = ["", "before", "after", "with", "any"];
const MAX_JSON_BYTES = 8_000;
const DATE = /^\d{4}-\d{2}-\d{2}$/;

type Common = { pattern: string; unit: RxUnit; food: FoodTiming; duration: Duration };
export type PayloadLine =
  | ({ kind: "brand"; code: string; substitution: boolean } & Common)
  | ({ kind: "generic"; generic: string; strength: string; dosageForm: string; substitution: boolean } & Common)
  | ({ kind: "free"; name: string } & Common);

export type RxPayload = { issueDate: string; followUp: string; lines: PayloadLine[] };

// ---------------------------------------------------------------- building

function durationCode(d: Duration): string {
  if (d.kind === "none") return "";
  if (d.kind === "continue") return "c";
  return `${d.n}${{ days: "d", weeks: "w", months: "m" }[d.unit]}`;
}

function parseDuration(code: unknown): Duration {
  if (code === "") return { kind: "none" };
  if (code === "c") return { kind: "continue" };
  const m = typeof code === "string" ? /^([1-9]\d{0,2})([dwm])$/.exec(code) : null;
  if (!m || Number(m[1]) > 365) throw new Error("duration");
  return { kind: "fixed", n: Number(m[1]), unit: ({ d: "days", w: "weeks", m: "months" } as const)[m[2] as "d"] };
}

export function toPayload(lines: RxLine[], issueDate: string, followUp: string): RxPayload {
  return {
    issueDate,
    followUp,
    lines: lines.map((line): PayloadLine => {
      const common = { pattern: line.pattern.trim().slice(0, 40), unit: line.unit, food: line.food, duration: line.duration };
      const s = line.source;
      if (s.kind === "brand") return { kind: "brand", code: s.code, substitution: line.substitution, ...common };
      if (s.kind === "generic") {
        return {
          kind: "generic",
          generic: s.generic,
          strength: s.strength,
          dosageForm: s.dosageForm,
          substitution: line.substitution,
          ...common,
        };
      }
      return { kind: "free", name: s.name.slice(0, MAX_FREE_NAME), ...common };
    }),
  };
}

/** The exact text that is hashed, signed and put in the QR (compact arrays, fixed key order). */
export function canonical(payload: RxPayload): string {
  const l = payload.lines.map((x) => {
    const tail = [x.pattern, RX_UNITS.indexOf(x.unit), FOODS.indexOf(x.food), durationCode(x.duration)];
    if (x.kind === "brand") return [Number(x.code.slice(2)), ...tail, x.substitution ? 1 : 0];
    if (x.kind === "generic") return ["g", x.generic, x.strength, x.dosageForm, ...tail, x.substitution ? 1 : 0];
    return ["t", x.name, ...tail];
  });
  return JSON.stringify({ v: PAYLOAD_VERSION, d: payload.issueDate, f: payload.followUp, l });
}

// ---------------------------------------------------------------- reading (strict: bad input throws)

function str(value: unknown, max: number, allowEmpty = true): string {
  if (typeof value !== "string" || value.length > max || (!allowEmpty && !value.trim())) throw new Error("text");
  return value;
}

function index<T>(list: readonly T[], value: unknown): T {
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0 || value >= list.length) throw new Error("index");
  return list[value];
}

function flag(value: unknown): boolean {
  if (value !== 0 && value !== 1) throw new Error("flag");
  return value === 1;
}

function common(pattern: unknown, unit: unknown, food: unknown, duration: unknown): Common {
  return { pattern: str(pattern, 40), unit: index(RX_UNITS, unit), food: index(FOODS, food), duration: parseDuration(duration) };
}

export function parseCanonical(text: string): RxPayload {
  const data = JSON.parse(text) as { v?: unknown; d?: unknown; f?: unknown; l?: unknown };
  if (!data || typeof data !== "object" || data.v !== PAYLOAD_VERSION) throw new Error("version");
  const issueDate = str(data.d, 10);
  const followUp = str(data.f, 10);
  if (!DATE.test(issueDate) || (followUp && !DATE.test(followUp))) throw new Error("date");
  if (!Array.isArray(data.l) || data.l.length === 0 || data.l.length > MAX_LINES) throw new Error("lines");
  const lines = data.l.map((raw: unknown): PayloadLine => {
    if (!Array.isArray(raw)) throw new Error("line");
    if (typeof raw[0] === "number") {
      if (raw.length !== 6 || !Number.isInteger(raw[0]) || raw[0] < 1 || raw[0] > 99_999) throw new Error("brand");
      return { kind: "brand", code: `BR${String(raw[0]).padStart(5, "0")}`, substitution: flag(raw[5]), ...common(raw[1], raw[2], raw[3], raw[4]) };
    }
    if (raw[0] === "g" && raw.length === 9) {
      return {
        kind: "generic",
        generic: str(raw[1], 200, false),
        strength: str(raw[2], 50, false),
        dosageForm: str(raw[3], 50, false),
        substitution: flag(raw[8]),
        ...common(raw[4], raw[5], raw[6], raw[7]),
      };
    }
    if (raw[0] === "t" && raw.length === 6) {
      return { kind: "free", name: str(raw[1], MAX_FREE_NAME, false), ...common(raw[2], raw[3], raw[4], raw[5]) };
    }
    throw new Error("kind");
  });
  return { issueDate, followUp, lines };
}

// ---------------------------------------------------------------- bytes

function toBase64Url(bytes: Uint8Array): string {
  let binary = "";
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function fromBase64Url(text: string): Uint8Array {
  if (!/^[A-Za-z0-9_-]*$/.test(text)) throw new Error("base64");
  const binary = atob(text.replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(binary, (c) => c.charCodeAt(0));
}

async function pipe(bytes: Uint8Array, stream: CompressionStream | DecompressionStream, max = Infinity): Promise<Uint8Array> {
  const reader = new Blob([bytes as BlobPart]).stream().pipeThrough(stream).getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.length;
    if (size > max) {
      await reader.cancel();
      throw new Error("too large");
    }
    chunks.push(value);
  }
  const out = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    out.set(chunk, offset);
    offset += chunk.length;
  }
  return out;
}

export async function encodePayload(text: string): Promise<string> {
  const bytes = new TextEncoder().encode(text);
  if (typeof CompressionStream === "function") return "z" + toBase64Url(await pipe(bytes, new CompressionStream("deflate-raw")));
  return "p" + toBase64Url(bytes);
}

/** The canonical JSON text inside an encoded payload (throws on anything unexpected). */
export async function decodePayload(encoded: string): Promise<string> {
  if (encoded.length > 4_000) throw new Error("too long");
  const kind = encoded[0];
  const bytes = fromBase64Url(encoded.slice(1));
  let raw: Uint8Array;
  if (kind === "z") {
    if (typeof DecompressionStream !== "function") throw new Error("unsupported");
    raw = await pipe(bytes, new DecompressionStream("deflate-raw"), MAX_JSON_BYTES);
  } else if (kind === "p") {
    raw = bytes;
  } else {
    throw new Error("kind");
  }
  if (raw.length > MAX_JSON_BYTES) throw new Error("too large");
  return new TextDecoder("utf-8", { fatal: true }).decode(raw);
}

export async function sha256Hex(text: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

// ---------------------------------------------------------------- the link

export type RxSignature = { doctorId: number; issuedAt: number; sig: string };

export function buildRxLink(origin: string, encoded: string, s: RxSignature): string {
  return `${origin}/rx#${encoded}.${s.doctorId}.${s.issuedAt}.${s.sig}`;
}

/** The parts after "#" (null when the link is not one of ours). */
export function parseRxFragment(hash: string): ({ encoded: string } & RxSignature) | null {
  const parts = hash.replace(/^#/, "").split(".");
  if (parts.length !== 4) return null;
  const [encoded, doctorId, issuedAt, sig] = parts;
  if (!/^[zp][A-Za-z0-9_-]+$/.test(encoded) || !/^[1-9]\d{0,9}$/.test(doctorId) || !/^\d{1,12}$/.test(issuedAt)) return null;
  if (!/^[A-Za-z0-9_-]{43}$/.test(sig)) return null;
  return { encoded, doctorId: Number(doctorId), issuedAt: Number(issuedAt), sig };
}

/** Everything the /rx page needs from a link: the payload and the exact text that was signed. */
export async function readRxLink(hash: string): Promise<{ payload: RxPayload; text: string; signature: RxSignature }> {
  const parts = parseRxFragment(hash);
  if (!parts) throw new Error("link");
  const { encoded, ...signature } = parts;
  const text = await decodePayload(encoded);
  return { payload: parseCanonical(text), text, signature };
}
