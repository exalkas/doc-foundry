/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  images: {
    domains: ["localhost"],
  },
  // /api/* is proxied by app/api/[...path]/route.ts (reliable with App Router + client fetch).
};

module.exports = nextConfig;
