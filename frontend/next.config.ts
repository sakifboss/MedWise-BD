import type { NextConfig } from "next";

// Where the FastAPI backend lives. Server components call it directly; the browser
// reaches it through the /api rewrite below, so no CORS setup is needed.
const API_URL = process.env.API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
};

export default nextConfig;
