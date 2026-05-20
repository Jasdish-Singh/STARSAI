import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["icon-192.png", "icon-512.png"],
      manifest: false,
      workbox: {
        maximumFileSizeToCacheInBytes: 4 * 1024 * 1024,
        globPatterns: ["**/*.{js,css,html,json,png,svg,woff2}"],
        runtimeCaching: [
          {
            urlPattern: /\/data\/scores\.json$/,
            handler: "CacheFirst",
            options: {
              cacheName: "scores-cache",
              expiration: { maxEntries: 1, maxAgeSeconds: 86400 },
            },
          },
          {
            urlPattern: /\/data\/provenance\.json$/,
            handler: "NetworkFirst",
            options: {
              cacheName: "provenance-cache",
              expiration: { maxEntries: 50, maxAgeSeconds: 86400 },
            },
          },
          {
            urlPattern: /^https:\/\/.*\.tiles\.mapbox\.com\/.*/,
            handler: "CacheFirst",
            options: {
              cacheName: "tile-cache",
              expiration: { maxEntries: 500, maxAgeSeconds: 604800 },
            },
          },
        ],
      },
    }),
  ],
  publicDir: "public",
  server: { host: "0.0.0.0", port: 5173 },
});
