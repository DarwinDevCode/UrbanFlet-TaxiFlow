import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";
import { VitePWA } from "vite-plugin-pwa";

// Web conductor (arquitectura_software.md §6 punto 7): debe operar como PWA
// instalada y en primer plano durante el turno. Wake Lock + buffer de traza
// en IndexedDB se implementan en Fase 3 (CU-O07) — este shell solo cubre
// instalabilidad, manifest y auth (alcance de Fase 0).
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["icon.svg"],
      manifest: {
        name: "UrbanFleet TaxiFlow — Conductor",
        short_name: "TaxiFlow Conductor",
        description: "Gestiona tu turno, ofertas de viaje y navegación.",
        theme_color: "#b5760a",
        background_color: "#f7f7f8",
        display: "standalone",
        start_url: "/",
        icons: [{ src: "icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any maskable" }],
      },
    }),
  ],
  server: { port: 5174 },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/setupTests.ts"],
    globals: true,
  },
});
