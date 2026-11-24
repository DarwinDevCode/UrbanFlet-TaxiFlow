import { AuthProvider, aplicarSidebarTonoInicial, aplicarTamanoTextoInicial, aplicarTemaInicial, configureApiClient, configureGoogleMapsApiKey } from "@urbanflet/shared-ui";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";

configureApiClient(import.meta.env.VITE_API_URL ?? "http://localhost:8000");
configureGoogleMapsApiKey(import.meta.env.VITE_GOOGLE_MAPS_API_KEY ?? "");
aplicarTemaInicial();
aplicarTamanoTextoInicial();
aplicarSidebarTonoInicial();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AuthProvider>
      <App />
    </AuthProvider>
  </StrictMode>,
);
