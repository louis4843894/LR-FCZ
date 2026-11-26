import type { NextConfig } from "next";
const nextConfig: NextConfig = {
  distDir: process.env.LR_NEXT_DIST_DIR ?? ".next",
  devIndicators: false,
  // Keep framework upgrades separate from the local game-data integration task.
  experimental: { agentUpgrade: false },
};
export default nextConfig;
