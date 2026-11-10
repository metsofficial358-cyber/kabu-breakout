import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Docker のビルド時だけ standalone 出力（ローカルの next start では使わない）
  output: process.env.NEXT_OUTPUT === "standalone" ? "standalone" : undefined,
  reactStrictMode: true,
};

export default nextConfig;
