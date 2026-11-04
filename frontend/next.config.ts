import type { NextConfig } from "next";

// Where the FastAPI backend lives. Server components call it directly; the browser
// reaches it through the /api rewrite below, so no CORS setup is needed.
const API_URL = process.env.API_URL ?? "http://localhost:8000";

// Sent with every response. The Content-Security-Policy is per request (nonce), in src/proxy.ts.
const SECURITY_HEADERS = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  // Other sites see only our origin, never a page URL (share links carry the medicine list).
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  // Microphone for voice search only; the prescription photo uses the file picker, not the camera API.
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(self), geolocation=(), payment=(), usb=(), browsing-topics=()",
  },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
];

const nextConfig: NextConfig = {
  // Only the Docker build sets NEXT_OUTPUT (standalone server); Vercel and local builds are unchanged.
  output: process.env.NEXT_OUTPUT === "standalone" ? "standalone" : undefined,
  poweredByHeader: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
  async headers() {
    return [
      { source: "/:path*", headers: SECURITY_HEADERS },
      // Browsers must always fetch the latest service worker, never a cached copy.
      { source: "/sw.js", headers: [{ key: "Cache-Control", value: "no-cache, no-store, must-revalidate" }] },
    ];
  },
};

export default nextConfig;
