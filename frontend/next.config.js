/** @type {import('next').NextConfig} */
const withPWA = require("next-pwa")({
  dest: "public",
  register: true,
  skipWaiting: true,
  disable: process.env.NODE_ENV === "development",
  fallbacks: {
    document: "/offline.html",
  },
  runtimeCaching: [
    {
      urlPattern: /^https:\/\/basemaps\.cartocdn\.com\/.*/i,
      handler: "CacheFirst",
      options: {
        cacheName: "map-tiles-cache",
        expiration: {
          maxEntries: 200,
          maxAgeSeconds: 60 * 60 * 24, // 24시간
        },
      },
    },
    {
      urlPattern: /^\/api\/.*/i,
      handler: "NetworkFirst",
      options: {
        cacheName: "api-cache",
        expiration: {
          maxEntries: 100,
          maxAgeSeconds: 60 * 5, // 5분
        },
      },
    },
  ],
});

const path = require("path");

const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
  swcMinify: true,
  poweredByHeader: false,
  experimental: {
    optimizeCss: true,
  },
  webpack: (config, { isServer, webpack }) => {
    if (!isServer) {
      // 모던 브라우저 (Chrome 93+, Safari 15.4+) 에서 불필요한 폴리필 제거 → ~11KB 절감
      config.plugins.push(
        new webpack.NormalModuleReplacementPlugin(
          /[\\/]polyfill-module\.js$/,
          path.join(__dirname, "lib/empty-polyfill.js")
        )
      );
    }
    return config;
  },
  typescript: {
    ignoreBuildErrors: false,
  },
  eslint: {
    ignoreDuringBuilds: false,
  },
  images: {
    domains: [],
    formats: ["image/webp"],
    minimumCacheTTL: 86400,
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains; preload" },
          { key: "Cross-Origin-Opener-Policy", value: "same-origin-allow-popups" },
          { key: "Cross-Origin-Resource-Policy", value: "cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(self)" },
          {
            key: "Content-Security-Policy",
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-inline' https://js.dodo.dev https://*.firebaseio.com https://apis.google.com https://www.gstatic.com https://www.googletagmanager.com",
              "style-src 'self' 'unsafe-inline' https://unpkg.com",
              "img-src 'self' data: blob: https:",
              "font-src 'self' data: https://fonts.gstatic.com",
              "connect-src 'self' https://api.wewantpeace.live https://backend-production-3af7.up.railway.app https://*.firebaseio.com https://*.googleapis.com https://*.cartocdn.com https://identitytoolkit.googleapis.com https://securetoken.googleapis.com https://firebaseinstallations.googleapis.com https://www.gstatic.com https://accounts.google.com https://appleid.apple.com https://kauth.kakao.com https://www.google-analytics.com https://www.googletagmanager.com",
              "frame-src https://checkout.dodopayments.com https://accounts.google.com https://appleid.apple.com https://*.firebaseapp.com",
              "worker-src 'self' blob:",
              "frame-ancestors 'none'",
            ].join("; "),
          },
        ],
      },
      {
        source: "/llms.txt",
        headers: [
          { key: "Content-Type", value: "text/plain; charset=utf-8" },
          { key: "Cache-Control", value: "public, max-age=3600, s-maxage=86400" },
          { key: "X-Robots-Tag", value: "noindex" },
        ],
      },
      {
        source: "/.well-known/llms.txt",
        headers: [
          { key: "Content-Type", value: "text/plain; charset=utf-8" },
          { key: "Cache-Control", value: "public, max-age=3600, s-maxage=86400" },
        ],
      },
    ];
  },
};

module.exports = withPWA(nextConfig);
