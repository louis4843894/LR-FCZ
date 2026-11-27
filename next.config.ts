import type { NextConfig } from "next";
const nextConfig: NextConfig = {
  distDir: process.env.LR_NEXT_DIST_DIR ?? ".next",
  devIndicators: false,
  outputFileTracingIncludes: { '/*': ['./data/site-display/*.json.gz'] },
  outputFileTracingExcludes: { '/*': ['./data/site-display/guilds.json.gz', './data/site-display/guild-*.json.gz', './data/local/**', './data/research/**', './data/raw/**', './data/extracted/**', './data/normalized/*.private.*', './data/normalized/*reference-preview.json'] },
  // Keep framework upgrades separate from the local game-data integration task.
  experimental: { agentUpgrade: false },
};
export default nextConfig;
