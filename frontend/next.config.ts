import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  eslint: {
    // Linting is run separately; do not fail production builds on lint errors.
    ignoreDuringBuilds: true,
  },
};

export default nextConfig;
