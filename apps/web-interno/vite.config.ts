import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// A diferencia de web-pasajero y web-conductor, la arquitectura solo llama
// "PWA" explícitamente a los portales de pasajero y conductor (línea 5, §6);
// el portal interno queda agrupado como "responsivo" sin confirmar
// instalabilidad — se deja como SPA responsiva sin manifest/service worker
// hasta que el cliente lo confirme (no se asume comportamiento no
// especificado).
export default defineConfig({
  plugins: [react()],
  server: { port: 5175 },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/setupTests.ts"],
    globals: true,
  },
});
