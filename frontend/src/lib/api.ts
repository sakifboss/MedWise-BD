import type { Lang } from "@/i18n/dictionaries";

import type { components } from "./api-schema";
import type { PharmaciesData } from "./pharmacies";
import type { SymptomAnswers, SymptomResult, SymptomSetup } from "./symptom-guide";

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
export type InteractionCheckRequest = Schemas["InteractionCheckRequest"];
export type InteractionCheckResponse = Schemas["InteractionCheckResponse"];
export type FoundInteraction = Schemas["InteractionOut"];
export type CheckedMedicine = Schemas["CheckedMedicine"];
export type ManufacturerListItem = Schemas["ManufacturerListItem"];
export type ManufacturerDetail = Schemas["ManufacturerDetail"];
export type FactorKey = Schemas["FactorDetail"]["key"];
export type CatalogStats = Schemas["CatalogStats"];
export type GenericListItem = Schemas["GenericListItem"];
export type RequestSource = Schemas["MedicineRequestIn"]["source"];
export type BrandIndex = Schemas["BrandIndex"];
export type ReportReason = Schemas["DataReportIn"]["reason"];
export type DoctorProfile = Schemas["DoctorOut"];
export type DoctorExport = Schemas["DoctorExport"];
export type DoctorSignup = Schemas["SignupIn"];
export type DoctorProfileIn = Schemas["ProfileIn"];
export type DoctorChamberIn = Schemas["ChamberIn"];
export type RxSignOut = Schemas["RxSignOut"];
export type TemplateIn = Schemas["TemplateIn"];
export type TemplateOut = Schemas["TemplateOut"];
export type TemplateSummary = Schemas["TemplateSummary"];
export type RxVerifyIn = Schemas["RxVerifyIn"];
export type RxVerifyOut = Schemas["RxVerifyOut"];

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

/** True when the server asked us to slow down (HTTP 429). */
export function isRateLimited(error: unknown): boolean {
  return error instanceof ApiError && error.status === 429;
}

/** The server could not be reached (no internet, or the connection dropped). */
export function isNetworkError(error: unknown): boolean {
  return error instanceof ApiError && error.code === "network_error";
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

function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

/**
 * Doctor accounts (Rx Pad). Browser only: the login lives in an HttpOnly cookie that the page's
 * scripts cannot read, sent with these same-site calls. Never used for anything about patients.
 */
export const doctorApi = {
  me: () => request<DoctorProfile>("/api/doctor/me", { cache: "no-store" }),
  signup: (body: DoctorSignup) => post<DoctorProfile>("/api/doctor/signup", body),
  login: (email: string, password: string) => post<DoctorProfile>("/api/doctor/login", { email, password }),
  logout: () => post<{ ok: boolean }>("/api/doctor/logout", {}),
  logoutEverywhere: () => post<{ ok: boolean }>("/api/doctor/logout-all", {}),
  saveProfile: (body: DoctorProfileIn) => post<DoctorProfile>("/api/doctor/profile", body),
  saveChambers: (chambers: DoctorChamberIn[]) => post<DoctorProfile>("/api/doctor/chambers", { chambers }),
  changePassword: (currentPassword: string, newPassword: string) =>
    post<{ ok: boolean }>("/api/doctor/password", { current_password: currentPassword, new_password: newPassword }),
  resetPassword: (token: string, newPassword: string) =>
    post<{ ok: boolean }>("/api/doctor/reset", { token, new_password: newPassword }),
  exportData: () => request<DoctorExport>("/api/doctor/export", { cache: "no-store" }),
  deleteAccount: (password: string) => post<{ ok: boolean }>("/api/doctor/delete", { password }),
  /** Sends only the SHA-256 of the prescription's QR payload; the medicines stay in the browser. */
  signRx: (hash: string) => post<RxSignOut>("/api/doctor/rx/sign", { hash }),
  /** The doctor's own templates and favourite tests (never patient details). */
  templates: () => request<TemplateSummary[]>("/api/doctor/templates", { cache: "no-store" }),
  template: (id: number) => request<TemplateOut>(`/api/doctor/templates/${id}`, { cache: "no-store" }),
  createTemplate: (body: TemplateIn) => post<TemplateOut>("/api/doctor/templates", body),
  updateTemplate: (id: number, body: TemplateIn) => post<TemplateOut>(`/api/doctor/templates/${id}`, body),
  renameTemplate: (id: number, name: string) => post<TemplateSummary>(`/api/doctor/templates/${id}/rename`, { name }),
  deleteTemplate: (id: number) => post<{ ok: boolean }>(`/api/doctor/templates/${id}/delete`, {}),
  favouriteTests: () => request<{ tests: string[] }>("/api/doctor/favourite-tests", { cache: "no-store" }),
  saveFavouriteTests: (tests: string[]) => post<{ tests: string[] }>("/api/doctor/favourite-tests", { tests }),
};

/** The public /rx page's check: only doctor id, issue time, payload hash and signature are sent. */
export function verifyRx(body: RxVerifyIn): Promise<RxVerifyOut> {
  return post<RxVerifyOut>("/api/rx/verify", body);
}

export const api = {
  search(q: string, options: { limit?: number; signal?: AbortSignal } = {}) {
    const params = new URLSearchParams({ q, limit: String(options.limit ?? 12) });
    return request<SearchResponse>(`/api/search?${params}`, { signal: options.signal });
  },
  manufacturers() {
    return request<ManufacturerListItem[]>("/api/manufacturers");
  },
  manufacturer(id: number) {
    return request<ManufacturerDetail>(`/api/manufacturers/${id}`);
  },
  /** `lang` picks the language of generated text (reasons, interaction descriptions). */
  generic(id: number, lang: Lang = "en") {
    return request<GenericDetail>(`/api/generics/${id}?lang=${lang}`);
  },
  genericRanking(id: number, strength: string, dosageForm: string, lang: Lang = "en") {
    const params = new URLSearchParams({ strength, dosage_form: dosageForm, lang });
    return request<AlternativesResponse>(`/api/generics/${id}/ranking?${params}`);
  },
  /** A brand's ranking group, by its stable code (BR00042) or, for old links, its id. */
  alternatives(brandRef: string | number, lang: Lang = "en") {
    return request<AlternativesResponse>(`/api/alternatives/${encodeURIComponent(String(brandRef))}?lang=${lang}`);
  },
  /** Every brand with its code (cached by the browser for an hour). */
  brandIndex() {
    return request<BrandIndex>("/api/brands/index");
  },
  checkInteractions(body: InteractionCheckRequest, signal?: AbortSignal, lang: Lang = "en") {
    return request<InteractionCheckResponse>(`/api/interactions/check?lang=${lang}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
  },
  generics() {
    return request<GenericListItem[]>("/api/generics");
  },
  stats() {
    return request<CatalogStats>("/api/stats");
  },
  /** The emergency checklist (NHS wording) and the specialties, in the page language. */
  symptomSetup(lang: Lang = "en") {
    return request<SymptomSetup>(`/api/symptom-guide/setup?lang=${lang}`);
  },
  /** Only the person's text and answers are sent; nothing from My Medicines. Not stored. */
  symptomGuide(answers: SymptomAnswers) {
    return request<SymptomResult>("/api/symptom-guide", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(answers),
    });
  },
  /** The whole pharmacy list; no position is sent (distances are worked out in the browser). */
  pharmacies() {
    return request<PharmaciesData>("/api/pharmacies?city=sylhet");
  },
  /** "Request this medicine": only the text and where it came from are sent (and stored). */
  requestMedicine(query: string, source: RequestSource) {
    return request<Schemas["MedicineRequestSaved"]>("/api/requests", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, source }),
    });
  },
  /** "Report a problem": only the brand and a fixed reason are sent (and stored, with the day). */
  reportProblem(brandId: number, reason: ReportReason) {
    return request<Schemas["DataReportSaved"]>("/api/reports", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ brand_id: brandId, reason }),
    });
  },
  readPrescription(image: Blob, filename: string) {
    const form = new FormData();
    form.append("image", image, filename);
    return request<PrescriptionResponse>("/api/prescription", { method: "POST", body: form });
  },
};
