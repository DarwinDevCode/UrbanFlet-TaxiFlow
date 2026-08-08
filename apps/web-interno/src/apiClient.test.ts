// Red de seguridad sobre el interceptor de 401 de `apiFetch`
// (`apps/shared-ui/src/api/client.ts`). Vive en web-interno y no en
// shared-ui porque shared-ui no tiene infraestructura de tests propia (solo
// lint, ver CLAUDE.md §5) y se consume como fuente TS vía workspace.
//
// Fija el comportamiento corregido tras el bug real de la estampida de
// refresh: N peticiones concurrentes que expiran a la vez deben producir UNA
// sola llamada a `POST /auth/refresh`, no N (cada una registraba una sesión
// nueva en Redis — sesiones fantasma en "Mis sesiones", Módulo 1.4).
import { apiFetch, configureApiClient } from "@urbanflet/shared-ui";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const BASE = "http://backend.test";

function respuesta(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: String(status),
    json: async () => body,
  } as Response;
}

describe("apiFetch — interceptor de 401", () => {
  beforeEach(() => {
    configureApiClient(BASE);
    localStorage.setItem("urbanflet.access_token", "access-viejo");
    localStorage.setItem("urbanflet.refresh_token", "refresh-valido");
  });

  afterEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("renueva una sola vez para N peticiones concurrentes que expiran a la vez", async () => {
    let refreshes = 0;
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith("/auth/refresh")) {
        refreshes += 1;
        // Renovación deliberadamente lenta: deja a las otras peticiones
        // chocar con el 401 mientras esta sigue en vuelo. Es justo la
        // ventana en la que la versión anterior disparaba una llamada a
        // /auth/refresh por cada petición.
        await new Promise((r) => setTimeout(r, 10));
        return respuesta(200, { access_token: "access-nuevo", refresh_token: "refresh-nuevo" });
      }
      const token = (init?.headers as Record<string, string>)?.Authorization;
      if (token !== "Bearer access-nuevo") return respuesta(401, { code: "INVALID_TOKEN" });
      return respuesta(200, { ok: true, url });
    });
    vi.stubGlobal("fetch", fetchMock);

    // Las 3 peticiones exactas del incidente reportado.
    const resultados = await Promise.all([
      apiFetch<{ ok: boolean }>("/notificaciones/mias?limite=1"),
      apiFetch<{ ok: boolean }>("/notificaciones/mias?limite=1"),
      apiFetch<{ ok: boolean }>("/usuarios?limit=20&offset=0"),
    ]);

    expect(resultados.every((r) => r.ok)).toBe(true);
    expect(refreshes).toBe(1);
    expect(localStorage.getItem("urbanflet.access_token")).toBe("access-nuevo");
  });

  it("reintenta sin renovar si otra petición ya había renovado el token", async () => {
    let refreshes = 0;
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith("/auth/refresh")) {
        refreshes += 1;
        return respuesta(200, { access_token: "access-nuevo", refresh_token: "refresh-nuevo" });
      }
      const token = (init?.headers as Record<string, string>)?.Authorization;
      if (token === "Bearer access-viejo") {
        // Simula que otra petición renovó mientras esta viajaba.
        localStorage.setItem("urbanflet.access_token", "access-nuevo");
        return respuesta(401, { code: "INVALID_TOKEN" });
      }
      return respuesta(200, { ok: true });
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiFetch<{ ok: boolean }>("/usuarios?limit=20&offset=0")).resolves.toEqual({ ok: true });
    expect(refreshes).toBe(0);
  });

  it("no borra los tokens si la renovación falla por red (corte transitorio)", async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (url.endsWith("/auth/refresh")) throw new TypeError("Failed to fetch");
      return respuesta(401, { code: "INVALID_TOKEN", message: "expirado" });
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiFetch("/notificaciones/mias?limite=1")).rejects.toThrow();
    expect(localStorage.getItem("urbanflet.refresh_token")).toBe("refresh-valido");
  });

  it("borra los tokens si el backend rechaza el refresh token", async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (url.endsWith("/auth/refresh")) return respuesta(401, { code: "INVALID_CREDENTIALS" });
      return respuesta(401, { code: "INVALID_TOKEN", message: "expirado" });
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiFetch("/usuarios?limit=20&offset=0")).rejects.toThrow();
    expect(localStorage.getItem("urbanflet.refresh_token")).toBeNull();
  });
});
