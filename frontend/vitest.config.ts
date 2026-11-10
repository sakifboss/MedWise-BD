import { fileURLToPath } from "node:url";

import { defineConfig } from "vitest/config";

// Unit tests for pure helpers in src/lib only (no DOM, no React, no network).
export default defineConfig({
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  test: {
    include: ["src/lib/**/*.test.ts"],
    environment: "node",
  },
});
