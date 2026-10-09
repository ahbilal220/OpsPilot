import type { NextConfig } from "next";
const staticExport = process.env.STATIC_EXPORT === "1";
const config: NextConfig = staticExport
  ? { output: "export" }
  : {
      output: "standalone",
      async rewrites() {
        return [
          {
            source: "/api/v1/:path*",
            destination: `${process.env.API_INTERNAL_URL ?? "http://localhost:8000"}/api/v1/:path*`,
          },
        ];
      },
    };
export default config;
