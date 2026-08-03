import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";
import { VitePWA } from "vite-plugin-pwa";

// Web pasajero (arquitectura_software.md línea 5): PWA responsiva instalable
// desde el navegador del teléfono, portal más simple de los tres.
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["icon.svg"],
      manifest: {
        name: "UrbanFleet TaxiFlow — Pasajero",
        short_name: "TaxiFlow Pasajero",
        description: "Solicita y sigue tus viajes con la cooperativa.",
        theme_color: "#1f6feb",
        background_color: "#f7f7f8",
        display: "standalone",
        start_url: "/",
        icons: [{ src: "icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any maskable" }],
      },
    }),
  ],
  server: { port: 5173 },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/setupTests.ts"],
    globals: true,
  },
});
