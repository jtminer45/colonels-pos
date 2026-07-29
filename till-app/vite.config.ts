import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

// The till app must be installable and fully usable with zero internet
// connection. VitePWA precaches the built app shell (JS/CSS/HTML/icons) so
// the tablet can open it offline. Menu data and sales still go through the
// FastAPI backend at API_BASE_URL (see src/api/client.ts) — on the same
// device today, on the local WiFi network once this moves to a Pi. That is
// a local-network dependency, not an internet dependency.
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["icons/*.png", "menu_photos/*.svg", "menu_photos/*.jpg", "logo.png"],
      manifest: {
        name: "Colonels Restaurant & Garden — Till",
        short_name: "Colonels Till",
        description: "Till / point-of-sale app for Colonels Restaurant & Garden",
        theme_color: "#0A0A0A",
        background_color: "#0A0A0A",
        display: "standalone",
        orientation: "landscape",
        start_url: "/",
        icons: [
          { src: "icons/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "icons/icon-512.png", sizes: "512x512", type: "image/png" },
          { src: "icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
      workbox: {
        // Precache the app shell + bundled photos/icons so the UI renders
        // fully offline. API calls to the backend are NOT cached here —
        // sales must always hit the live database, never a stale cache.
        globPatterns: ["**/*.{js,css,html,svg,png,jpg,ico}"],
        // Real menu photos push total precache size well past workbox's
        // default 2 MiB warning threshold — still small enough to cache
        // safely, just needs a higher explicit limit.
        maximumFileSizeToCacheInBytes: 10 * 1024 * 1024,
      },
    }),
  ],
  server: {
    port: 5173,
  },
});
