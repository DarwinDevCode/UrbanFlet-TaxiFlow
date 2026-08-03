// Red de seguridad para los flujos críticos de web-conductor ya verificados
// manualmente en navegador: aceptar/rechazar oferta (CU-O06) e iniciar/
// terminar turno (CU-O07). No busca cobertura completa — solo que estos
// caminos no se rompan en silencio con cambios futuros.
//
// DriverMap se mockea a propósito: usa Leaflet, que manipula el DOM de
// formas que jsdom no soporta y no es lo que estos tests necesitan probar
// (el mapa ya se verificó visualmente en navegador real).
import { AuthProvider } from "@urbanflet/shared-ui";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

vi.mock("./DriverMap", () => ({
  DriverMap: () => <div data-testid="driver-map-stub" />,
}));

function makeFakeAccessToken(payload: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: "none", typ: "JWT" }));
  const body = btoa(JSON.stringify(payload));
  return `${header}.${body}.signature`;
}

function loginComoConductor(usuarioId = "conductor-test-1") {
  localStorage.setItem("urbanflet.access_token", makeFakeAccessToken({ sub: usuarioId, roles: ["conductor"] }));
  localStorage.setItem("urbanflet.refresh_token", "refresh-token-test");
}

const OFERTA_FIXTURE = {
  viaje_id: "viaje-oferta-1",
  pasajero_nombre: "María López",
  pasajero_calificacion: 4.8,
  origen_lat: -0.18,
  origen_lon: -78.46,
  distancia_km: 1.2,
  tiene_destino: true,
  segundos_restantes: 20,
};

const VIAJE_ASIGNADO_FIXTURE = {
  id: "viaje-oferta-1",
  estado: "ASIGNADO",
  origen_lat: -0.18,
  origen_lon: -78.46,
  origen_direccion: "Av. Amazonas",
  destino_lat: -0.2,
  destino_lon: -78.5,
  destino_direccion: "Terminal Terrestre",
  ts_llegada_origen: null,
  km_recorridos: null,
  tarifa_final: null,
  calificacion_conductor_a_pasajero: null,
};

type Ruta = { method: string; path: string; status?: number; body?: unknown };

function mockFetch(handlers: Ruta[]) {
  const restantes = [...handlers];
  const llamadas: { method: string; path: string; body: unknown }[] = [];

  const responder = (status: number, body: unknown) => {
    return Promise.resolve({
      ok: status >= 200 && status < 300,
      status,
      json: async () => body,
    } as Response);
  };

  globalThis.fetch = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    const path = url.replace(/^https?:\/\/[^/]+/, "");
    const method = init?.method ?? "GET";
    llamadas.push({ method, path, body: init?.body ? JSON.parse(init.body as string) : undefined });

    const idx = restantes.findIndex((r) => r.method === method && path.startsWith(r.path));
    if (idx !== -1) {
      const [ruta] = restantes.splice(idx, 1);
      return responder(ruta.status ?? 200, ruta.body ?? null);
    }

    // Defaults para llamadas de fondo que no son el foco del test (reporte
    // de posición periódico, poll de oferta cuando el test no lo declara).
    if (method === "POST" && path.startsWith("/flota/posiciones")) {
      return responder(200, { aceptada: true, precision_baja: false });
    }
    if (method === "GET" && path.startsWith("/viajes/oferta-actual")) {
      return responder(200, null);
    }
    throw new Error(`Llamada a fetch no esperada en este test: ${method} ${path}`);
  }) as unknown as typeof fetch;

  return { llamadas };
}

function mockGeolocationExitoso(lat = -0.18, lon = -78.46) {
  Object.defineProperty(globalThis.navigator, "geolocation", {
    configurable: true,
    value: {
      getCurrentPosition: (success: PositionCallback) => {
        success({
          coords: { latitude: lat, longitude: lon, accuracy: 10, speed: null, heading: null },
        } as GeolocationPosition);
      },
    },
  });
}

function renderApp() {
  return render(
    <AuthProvider>
      <App />
    </AuthProvider>,
  );
}

beforeEach(() => {
  localStorage.clear();
  loginComoConductor();
  mockGeolocationExitoso();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("web-conductor — iniciar/terminar turno (CU-O07)", () => {
  it("inicia turno, pasa a DISPONIBLE y permite terminarlo de vuelta a FUERA_DE_LINEA", async () => {
    const { llamadas } = mockFetch([
      { method: "GET", path: "/viajes/conductor/activo", body: null },
      { method: "POST", path: "/flota/turno/iniciar", body: { estado_servicio: "DISPONIBLE" } },
      { method: "POST", path: "/flota/turno/terminar", body: { estado_servicio: "FUERA_DE_LINEA" } },
    ]);
    const user = userEvent.setup();

    renderApp();

    const botonIniciar = await screen.findByRole("button", { name: "Iniciar turno" });
    await user.click(botonIniciar);

    const botonTerminar = await screen.findByRole("button", { name: "Terminar turno" });
    expect(
      llamadas.some((c) => c.method === "POST" && c.path === "/flota/turno/iniciar"),
    ).toBe(true);

    await user.click(botonTerminar);

    expect(await screen.findByRole("button", { name: "Iniciar turno" })).toBeInTheDocument();
    expect(
      llamadas.some((c) => c.method === "POST" && c.path === "/flota/turno/terminar"),
    ).toBe(true);
  });
});

describe("web-conductor — aceptar/rechazar oferta (CU-O06)", () => {
  async function iniciarTurnoConOferta() {
    mockFetch([
      { method: "GET", path: "/viajes/conductor/activo", body: null },
      { method: "POST", path: "/flota/turno/iniciar", body: { estado_servicio: "DISPONIBLE" } },
      { method: "GET", path: "/viajes/oferta-actual", body: OFERTA_FIXTURE },
    ]);
    const user = userEvent.setup();
    renderApp();
    const botonIniciar = await screen.findByRole("button", { name: "Iniciar turno" });
    await user.click(botonIniciar);
    return user;
  }

  it("al aceptar, pide el viaje asignado y muestra la tarjeta de viaje en curso", async () => {
    const user = await iniciarTurnoConOferta();

    expect(await screen.findByText(/Nuevo viaje/)).toBeInTheDocument();
    expect(screen.getByText(/María López/)).toBeInTheDocument();

    const { llamadas } = mockFetch([
      { method: "POST", path: "/viajes/oferta/responder", body: { estado: "ASIGNADO" } },
      { method: "GET", path: "/viajes/conductor/activo", body: VIAJE_ASIGNADO_FIXTURE },
    ]);
    await user.click(screen.getByRole("button", { name: "Aceptar" }));

    expect(await screen.findByText("Viaje asignado")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Voy en camino" })).toBeInTheDocument();
    const respuesta = llamadas.find((c) => c.path === "/viajes/oferta/responder");
    expect(respuesta?.body).toEqual({ aceptar: true });
  });

  it("al rechazar, descarta la oferta y vuelve al panel de turno sin pedir el viaje asignado", async () => {
    const user = await iniciarTurnoConOferta();

    expect(await screen.findByText(/Nuevo viaje/)).toBeInTheDocument();

    const { llamadas } = mockFetch([{ method: "POST", path: "/viajes/oferta/responder", body: { estado: "OFERTADO" } }]);
    await user.click(screen.getByRole("button", { name: "Rechazar" }));

    await waitFor(() => expect(screen.queryByText(/Nuevo viaje/)).not.toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Terminar turno" })).toBeInTheDocument();
    const respuesta = llamadas.find((c) => c.path === "/viajes/oferta/responder");
    expect(respuesta?.body).toEqual({ aceptar: false });
    expect(llamadas.some((c) => c.path === "/viajes/conductor/activo")).toBe(false);
  });
});
