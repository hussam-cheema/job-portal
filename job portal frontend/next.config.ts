import type { NextConfig } from "next";

const localApiProxy = process.env.LOCAL_API_PROXY_URL?.replace(/\/$/, "");

const nextConfig: NextConfig = {
  output: "standalone",
  ...(localApiProxy
    ? {
        async rewrites() {
          return [
            {
              source: "/backend-api/:path*",
              destination: `${localApiProxy}/:path*`,
            },
          ];
        },
      }
    : {}),
};

export default nextConfig;
