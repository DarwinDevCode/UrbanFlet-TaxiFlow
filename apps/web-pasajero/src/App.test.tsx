// Red de seguridad para los flujos críticos de web-pasajero ya verificados
// manualmente en navegador (ver sesión de auditoría CU-O04/CU-O05): solicitar
// viaje (incluye A1 flujo principal, A2 error de ubicación, A3
// TRIP_ALREADY_ACTIVE), cancelar solicitud, y reintentar búsqueda tras
// SIN_CONDUCTOR (CU-O05 A3). No busca cobertura completa — solo que estos
// caminos no se rompan en silencio con cambios futuros.
//
// RideMap se mockea a propósito: usa Leaflet, que manipula el DOM de formas
// que jsdom no soporta (tiles, ResizeObserver, etc.) y no es lo que estos
// tests necesitan probar — el mapa en sí ya se verificó visualmente en
// navegador real. El origen se obtiene igual que en producción, vía
// navigator.geolocation (mockeado), que es lo que habilita el botón
// "Solicitar taxi" independientemente del mapa.
import { AuthProvider } from "@urbanflet/shared-ui";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

vi.mock("./RideMap", () => ({
  ALTO_MAPA: 480,
  RideMap: () => <div data-testid="ride-map-stub" />,
}));

function makeFakeAccessToken(payload: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: "none", typ: "JWT" }));
  const body = btoa(JSON.stringify(payload));
  return `${header}.${body}.signature`;
}

function loginComoPasajero(usuarioId = "pasajero-test-1") {
  localStorage.setItem("urbanflet.access_token", makeFakeAccessToken({ sub: usuarioId, roles: ["pasajero"] }));
  localStorage.setItem("urbanflet.refresh_token", "refresh-token-test");
}

interface ViajeFixture {
  id: string;
  estado: string;
  conductor_id: string | null;
  origen_lat: number;
  origen_lon: number;
  origen_direccion: string;
  destino_lat: number | null;
  destino_lon: number | null;
  destino_direccion: string | null;
  tarifa_estimada: number | null;
  tarifa_final: number | null;
  conductor_nombre: string | null;
  conductor_calificacion: number | null;
  vehiculo_placa: string | null;
  vehiculo_marca: string | null;
  vehiculo_color: string | null;
  ts_solicitud: string;
  ts_llegada_origen: string | null;
  calificacion_pasajero_a_conductor: null;
}

function crearViaje(overrides: Partial<ViajeFixture> = {}): ViajeFixture {
  return {
    id: "viaje-1",
    estado: "SOLICITADO",
    conductor_id: null,
    origen_lat: -0.18,
    origen_lon: -78.46,
    origen_direccion: "Ubicación actual",
    destino_lat: null,
    destino_lon: null,
    destino_direccion: null,
    tarifa_estimada: null,
    tarifa_final: null,
    conductor_nombre: null,
    conductor_calificacion: null,
    vehiculo_placa: null,
    vehiculo_marca: null,
    vehiculo_color: null,
    ts_solicitud: new Date().toISOString(),
    ts_llegada_origen: null,
    calificacion_pasajero_a_conductor: null,
    ...overrides,
  };
}

type Ruta = { method: string; path: string; status?: number; body?: unknown };

// Fetch mock por rutas: cada llamada real de la app pasa por aquí. Las
// llamadas de "fondo" que dispara VistaViaje al montar (tarifa vigente,
// taxis cercanos) tienen un default silencioso — solo lo que le importa a
// cada test se declara explícitamente vía `handlers`.
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

    // Defaults para llamadas de fondo que no son el foco del test.
    if (method === "GET" && path.startsWith("/parametros/vigente")) {
      return responder(200, { valores: { arrancada: 1, costo_km: 0.5, carrera_minima: 1.5 } });
    }
    if (method === "GET" && path.startsWith("/flota/cercanos")) {
      return responder(200, []);
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
        success({ coords: { latitude: lat, longitude: lon } } as GeolocationPosition);
      },
    },
  });
}

function mockGeolocationDenegado() {
  Object.defineProperty(globalThis.navigator, "geolocation", {
    configurable: true,
    value: {
      getCurrentPosition: (_success: PositionCallback, error: PositionErrorCallback) => {
        error({ code: 1, PERMISSION_DENIED: 1 } as GeolocationPositionError);
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
  loginComoPasajero();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("web-pasajero — solicitar viaje (CU-O04/CU-O05)", () => {
  it("flujo principal: crea el viaje con el origen geolocalizado y muestra el estado 'Buscando conductor…'", async () => {
    mockGeolocationExitoso();
    const { llamadas } = mockFetch([
      { method: "GET", path: "/viajes/activo", body: null },
      { method: "POST", path: "/viajes", body: crearViaje({ estado: "SOLICITADO" }) },
    ]);

    renderApp();
    const user = userEvent.setup();

    const boton = await screen.findByRole("button", { name: "Solicitar taxi" });
    await waitFor(() => expect(boton).toBeEnabled());
    await user.click(boton);

    expect(await screen.findByText("Buscando conductor…")).toBeInTheDocument();
    const post = llamadas.find((c) => c.method === "POST" && c.path === "/viajes");
    expect(post?.body).toMatchObject({ origen_lat: -0.18, origen_lon: -78.46 });
  });

  it("A2: si falla la geolocalización, muestra el error y el botón para reintentar ubicación", async () => {
    mockGeolocationDenegado();
    mockFetch([{ method: "GET", path: "/viajes/activo", body: null }]);

    renderApp();

    expect(
      await screen.findByText(/Activa el permiso de ubicación en tu navegador para continuar/),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reintentar ubicación" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Solicitar taxi" })).toBeDisabled();
  });

  it("A3: si ya hay un viaje activo (TRIP_ALREADY_ACTIVE), lo recupera y lo muestra en vez de un error", async () => {
    mockGeolocationExitoso();
    const viajeExistente = crearViaje({ id: "viaje-existente", estado: "OFERTADO" });
    const { llamadas } = mockFetch([
      { method: "GET", path: "/viajes/activo", body: null },
      { method: "POST", path: "/viajes", status: 409, body: { code: "TRIP_ALREADY_ACTIVE", message: "Ya tienes un viaje activo" } },
      { method: "GET", path: "/viajes/activo", body: viajeExistente },
    ]);
    const user = userEvent.setup();

    renderApp();
    const boton = await screen.findByRole("button", { name: "Solicitar taxi" });
    await waitFor(() => expect(boton).toBeEnabled());
    await user.click(boton);

    // El viaje recuperado se muestra directamente en el panel de viaje activo
    // (no en el mensaje "ya tenías un viaje en curso" de PanelSolicitar, que
    // solo aplicaría si el panel de solicitud siguiera visible).
    expect(await screen.findByText("Ofrecido a un conductor…")).toBeInTheDocument();
    expect(llamadas.filter((c) => c.path === "/viajes/activo")).toHaveLength(2);
  });
});

describe("web-pasajero — cancelar solicitud (CU-O04 A4)", () => {
  it("cancela el viaje SOLICITADO y vuelve a la pantalla de pedir un taxi", async () => {
    mockGeolocationExitoso();
    const viajeActivo = crearViaje({ estado: "SOLICITADO" });
    mockFetch([
      { method: "GET", path: "/viajes/activo", body: viajeActivo },
      { method: "POST", path: "/viajes/activo/cancelar", body: null },
    ]);
    const user = userEvent.setup();

    renderApp();

    const botonCancelar = await screen.findByRole("button", { name: "Cancelar solicitud" });
    await user.click(botonCancelar);

    expect(await screen.findByRole("button", { name: "Solicitar taxi" })).toBeInTheDocument();
  });
});

describe("web-pasajero — reintentar búsqueda tras SIN_CONDUCTOR (CU-O05 A3)", () => {
  it("al agotarse los reintentos de despacho, permite reintentar con el mismo origen/destino", async () => {
    mockGeolocationExitoso();
    const viajeAgotado = crearViaje({
      id: "viaje-agotado",
      estado: "SIN_CONDUCTOR",
      origen_direccion: "Av. Amazonas",
      destino_lat: -0.2,
      destino_lon: -78.5,
      destino_direccion: "Terminal Terrestre",
    });
    const viajeReintento = crearViaje({ id: "viaje-reintento", estado: "SIN_CONDUCTOR" });
    const { llamadas } = mockFetch([
      { method: "GET", path: "/viajes/activo", body: null },
      { method: "POST", path: "/viajes", body: viajeAgotado },
      { method: "POST", path: "/viajes", body: viajeReintento },
    ]);
    const user = userEvent.setup();

    renderApp();
    const botonSolicitar = await screen.findByRole("button", { name: "Solicitar taxi" });
    await waitFor(() => expect(botonSolicitar).toBeEnabled());
    await user.click(botonSolicitar);

    const botonReintentar = await screen.findByRole("button", { name: "Reintentar búsqueda" });
    await user.click(botonReintentar);

    await waitFor(() => {
      const posts = llamadas.filter((c) => c.method === "POST" && c.path === "/viajes");
      expect(posts).toHaveLength(2);
    });
    const posts = llamadas.filter((c) => c.method === "POST" && c.path === "/viajes");
    // El reintento reusa el origen/destino del viaje agotado devuelto por el
    // backend, no el estado local del formulario (que nunca se llenó aquí).
    expect(posts[1].body).toMatchObject({
      origen_lat: viajeAgotado.origen_lat,
      origen_lon: viajeAgotado.origen_lon,
      destino_lat: viajeAgotado.destino_lat,
      destino_lon: viajeAgotado.destino_lon,
    });
  });
});
