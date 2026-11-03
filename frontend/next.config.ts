import type { NextConfig } from "next";

// Where the FastAPI backend lives. Server components call it directly; the browser
// reaches it through the /api rewrite below, so no CORS setup is needed.
const API_URL = process.env.API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  // Only the Docker build sets NEXT_OUTPUT (standalone server); Vercel and local builds are unchanged.
  output: process.env.NEXT_OUTPUT === "standalone" ? "standalone" : undefined,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
  async headers() {
    // Browsers must always fetch the latest service worker, never a cached copy.
    return [{ source: "/sw.js", headers: [{ key: "Cache-Control", value: "no-cache, no-store, must-revalidate" }] }];
  },
};

export default nextConfig;
