import { defineConfig } from "vitest/config";

// Unit tests for pure helpers in src/lib only (no DOM, no React, no network).
export default defineConfig({
  test: {
    include: ["src/lib/**/*.test.ts"],
    environment: "node",
  },
});
