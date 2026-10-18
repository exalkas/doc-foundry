/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  images: {
    domains: ["localhost"],
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination:
          process.env.BACKEND_URL || "http://localhost:8000/api/:path*",
      },
    ];
  },
  webpack: (config, { isServer }) => {
    // Fix for pdfjs-dist: exclude canvas and other Node.js modules from client-side bundle
    if (!isServer) {
      config.resolve.fallback = {
        ...config.resolve.fallback,
        canvas: false,
        fs: false,
        path: false,
        stream: false,
        crypto: false,
      };
    }
    // Prevent pdfjs-dist from bundling Node.js modules (both server and client)
    config.resolve.alias = {
      ...config.resolve.alias,
      canvas: false,
    };
    return config;
  },
};

module.exports = nextConfig;
