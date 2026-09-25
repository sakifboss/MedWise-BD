import type { components } from "./api-schema";

type Schemas = components["schemas"];

export type SearchResponse = Schemas["SearchResponse"];
export type SearchResult = Schemas["SearchResult"];
export type GenericDetail = Schemas["GenericDetail"];
export type Presentation = Schemas["Presentation"];
export type InteractionSummary = Schemas["InteractionSummary"];
export type AlternativesResponse = Schemas["AlternativesResponse"];
export type RankedAlternative = Schemas["RankedAlternative"];
export type Severity = InteractionSummary["severity"];
export type PrescriptionResponse = Schemas["PrescriptionResponse"];
export type PrescriptionItem = Schemas["PrescriptionItem"];
export type MatchOption = Schemas["MatchOptionOut"];

type Envelope<T> = {
  data?: T | null;
  error?: { code: string; message: string } | null;
};

export class ApiError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function isNotFound(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404;
}

function baseUrl(): string {
  // Browser: same-origin /api is rewritten to the backend (see next.config.ts).
  if (typeof window !== "undefined") return "";
  return process.env.API_URL ?? "http://localhost:8000";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${baseUrl()}${path}`, {
      ...init,
      headers: { Accept: "application/json", ...init?.headers },
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    throw new ApiError("network_error", "Could not reach the MedWise server.", 0);
  }

  let body: Envelope<T>;
  try {
    body = (await response.json()) as Envelope<T>;
  } catch {
    throw new ApiError("bad_response", "The server sent an unexpected response.", response.status);
  }

  if (!response.ok || body.error || body.data == null) {
    throw new ApiError(
      body.error?.code ?? "http_error",
      body.error?.message ?? `Request failed (${response.status})`,
      response.status,
    );
  }
  return body.data;
}

export const api = {
  search(q: string, options: { limit?: number; signal?: AbortSignal } = {}) {
    const params = new URLSearchParams({ q, limit: String(options.limit ?? 12) });
    return request<SearchResponse>(`/api/search?${params}`, { signal: options.signal });
  },
  generic(id: number) {
    return request<GenericDetail>(`/api/generics/${id}`);
  },
  genericRanking(id: number, strength: string, dosageForm: string) {
    const params = new URLSearchParams({ strength, dosage_form: dosageForm });
    return request<AlternativesResponse>(`/api/generics/${id}/ranking?${params}`);
  },
  alternatives(brandId: number) {
    return request<AlternativesResponse>(`/api/alternatives/${brandId}`);
  },
  readPrescription(image: Blob, filename: string) {
    const form = new FormData();
    form.append("image", image, filename);
    return request<PrescriptionResponse>("/api/prescription", { method: "POST", body: form });
  },
};
