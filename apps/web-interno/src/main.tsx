import { AuthProvider, aplicarDensidadInicial, aplicarSidebarTonoInicial, aplicarTamanoTextoInicial, aplicarTemaInicial, configureApiClient } from "@urbanflet/shared-ui";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";

configureApiClient(import.meta.env.VITE_API_URL ?? "http://localhost:8000");
aplicarTemaInicial();
aplicarTamanoTextoInicial();
aplicarDensidadInicial();
aplicarSidebarTonoInicial();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AuthProvider>
      <App />
    </AuthProvider>
  </StrictMode>,
);
