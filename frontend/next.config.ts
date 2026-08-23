import type { NextConfig } from "next";

const apiInternalUrl = process.env.API_INTERNAL_URL ?? "http://localhost:8001";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/backend/:path*",
        destination: `${apiInternalUrl}/:path*`,
      },
      {
        // FastAPI's Swagger page requests this absolute URL.
        source: "/openapi.json",
        destination: `${apiInternalUrl}/openapi.json`,
      },
    ];
  },
};

export default nextConfig;
