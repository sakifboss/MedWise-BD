import { afterEach, describe, expect, it, vi } from "vitest";

import { CATALOG_REVALIDATE_SECONDS, catalog } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("catalog fetch options", () => {
  it("keep catalog answers on the server for 10 minutes, per deploy", () => {
    vi.stubEnv("VERCEL_DEPLOYMENT_ID", "dpl_123");
    expect(CATALOG_REVALIDATE_SECONDS).toBe(600);
    expect(catalog()).toEqual({ next: { revalidate: 600 }, headers: { "X-MedWise-Build": "dpl_123" } });
  });

  it("send no build header outside Vercel (Docker, local)", () => {
    vi.stubEnv("VERCEL_DEPLOYMENT_ID", undefined);
    vi.stubEnv("VERCEL_GIT_COMMIT_SHA", undefined);
    expect(catalog()).toEqual({ next: { revalidate: 600 }, headers: {} });
  });

  it("add nothing in the browser", () => {
    vi.stubGlobal("window", {});
    expect(catalog()).toEqual({});
  });
});
