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
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
  ts_programado: string | null;
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
    ts_programado: null,
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
    // Campana de notificaciones (Sección 4.2), montada globalmente en el
    // header de AppShell -- fetch de fondo en cada test.
    if (method === "GET" && path.startsWith("/notificaciones/mias")) {
      return responder(200, { items: [], total: 0, no_leidas: 0 });
    }
    // Direcciones favoritas (Sección 1.1) -- se cargan apenas VistaViaje
    // monta sin viaje activo, sin relación con el foco de la mayoría de
    // los tests existentes.
    if (method === "GET" && path.startsWith("/direcciones")) {
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

describe("web-pasajero — Programar un viaje (Sección 1.5 de ux_complementaria.md)", () => {
  it("al elegir 'Programar' y una fecha futura, envía ts_programado y muestra el estado 'Viaje programado'", async () => {
    mockGeolocationExitoso();
    // El valor esperado se calcula con la misma conversión local->ISO que
    // hace el propio componente (`new Date(valor).toISOString()`), en vez
    // de un literal fijo -- evita que el test dependa de la zona horaria
    // de la máquina donde corre.
    const valorLocal = "2030-01-01T10:00";
    const tsEsperado = new Date(valorLocal).toISOString();
    const viajeProgramado = crearViaje({ estado: "PROGRAMADO", ts_programado: tsEsperado });
    const { llamadas } = mockFetch([
      { method: "GET", path: "/viajes/activo", body: null },
      { method: "POST", path: "/viajes", body: viajeProgramado },
    ]);
    const user = userEvent.setup();

    renderApp();
    await user.click(await screen.findByRole("button", { name: "Programar" }));

    const inputFecha = await screen.findByLabelText("Fecha y hora");
    fireEvent.change(inputFecha, { target: { value: valorLocal } });

    const botonProgramar = screen.getByRole("button", { name: "Programar viaje" });
    await waitFor(() => expect(botonProgramar).toBeEnabled());
    await user.click(botonProgramar);

    expect(await screen.findByText("Viaje programado")).toBeInTheDocument();
    const post = llamadas.find((c) => c.method === "POST" && c.path === "/viajes");
    expect(post?.body).toMatchObject({ ts_programado: tsEsperado });
  });
});

describe("web-pasajero — Mi perfil (Sección 1.3 de ux_complementaria.md)", () => {
  it("edita el nombre propio exigiendo la contraseña actual", async () => {
    mockGeolocationExitoso();
    const perfil = {
      id: "pasajero-test-1",
      nombre: "Pasajera Original",
      telefono: "+593900000001",
      email: null,
      roles: ["pasajero"],
      fecha_registro: new Date().toISOString(),
      foto_url: null,
    };
    const { llamadas } = mockFetch([
      { method: "GET", path: "/viajes/activo", body: null },
      { method: "GET", path: "/perfil", body: perfil },
      { method: "GET", path: "/perfil/sesiones", body: [] },
      { method: "PATCH", path: "/perfil", body: { ...perfil, nombre: "Pasajera Actualizada" } },
    ]);
    const user = userEvent.setup();

    renderApp();
    await user.click(await screen.findByRole("button", { name: "Mi perfil" }));

    await user.click(await screen.findByRole("button", { name: "Editar" }));
    const nombre = screen.getByLabelText("Nombre");
    await user.clear(nombre);
    await user.type(nombre, "Pasajera Actualizada");
    await user.type(screen.getByLabelText("Contraseña actual (para confirmar el cambio)"), "clave-actual");
    await user.click(screen.getByRole("button", { name: "Guardar" }));

    await waitFor(() => {
      const patch = llamadas.find((c) => c.method === "PATCH" && c.path === "/perfil");
      expect(patch?.body).toMatchObject({ nombre: "Pasajera Actualizada", password_actual: "clave-actual" });
    });
    expect(await screen.findByText("Datos actualizados.")).toBeInTheDocument();
  });
});

describe("web-pasajero — Ajustes (Sección 1.4 de ux_complementaria.md)", () => {
  it("cambia el tema a oscuro y lo aplica al documento", async () => {
    mockGeolocationExitoso();
    const prefsBase = {
      tema: "claro",
      densidad_tablas: "comoda",
      notificaciones_push: {},
      sonido_oferta: true,
      vibracion_oferta: true,
      recordatorio_turno_hora: null,
    };
    mockFetch([
      { method: "GET", path: "/viajes/activo", body: null },
      { method: "GET", path: "/preferencias", body: prefsBase },
      { method: "PATCH", path: "/preferencias", body: { ...prefsBase, tema: "oscuro" } },
    ]);
    const user = userEvent.setup();

    renderApp();
    await user.click(await screen.findByRole("button", { name: "Ajustes" }));

    const selectTema = await screen.findByLabelText("Tema");
    await user.selectOptions(selectTema, "oscuro");

    await waitFor(() => {
      expect(document.documentElement.dataset.theme).toBe("dark");
    });
  });
});

describe("web-pasajero — campana de notificaciones (Sección 4.2 de ux_complementaria.md)", () => {
  it("muestra el contador de no leídas y lo baja al marcar una como leída", async () => {
    mockGeolocationExitoso();
    const notificacion = {
      id: "notif-1",
      tipo: "VIAJE_ASIGNADO",
      categoria: "viaje",
      payload: { viaje_id: "v-1" },
      ts: new Date().toISOString(),
      leida: false,
    };
    const { llamadas } = mockFetch([
      { method: "GET", path: "/viajes/activo", body: null },
      { method: "GET", path: "/notificaciones/mias", body: { items: [], total: 1, no_leidas: 1 } },
      { method: "GET", path: "/notificaciones/mias", body: { items: [notificacion], total: 1, no_leidas: 1 } },
      { method: "PATCH", path: "/notificaciones/mias/notif-1/leida", body: { ...notificacion, leida: true } },
    ]);
    const user = userEvent.setup();

    renderApp();
    expect(await screen.findByText("1")).toBeInTheDocument();

    await user.click(await screen.findByRole("button", { name: "Bandeja de notificaciones" }));
    expect(await screen.findByText("Se asignó un conductor a tu viaje")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Marcar leída" }));

    await waitFor(() => {
      const patch = llamadas.find((c) => c.method === "PATCH" && c.path === "/notificaciones/mias/notif-1/leida");
      expect(patch).toBeDefined();
    });
    expect(screen.queryByRole("button", { name: "Marcar leída" })).not.toBeInTheDocument();
  });
});

describe("web-pasajero — Direcciones favoritas (Sección 1.1 de ux_complementaria.md)", () => {
  it("un toque en una dirección favorita fija el destino sin tocar el mapa", async () => {
    mockGeolocationExitoso();
    const favorita = { id: "fav-1", etiqueta: "Casa", direccion: "Casa color melón", lat: -0.2, lon: -78.5 };
    const { llamadas } = mockFetch([
      { method: "GET", path: "/viajes/activo", body: null },
      { method: "GET", path: "/direcciones", body: [favorita] },
      { method: "POST", path: "/viajes", body: crearViaje({ estado: "SOLICITADO" }) },
    ]);
    const user = userEvent.setup();

    renderApp();
    const chip = await screen.findByRole("button", { name: "Casa" });
    await user.click(chip);

    expect(await screen.findByDisplayValue("Casa color melón")).toBeInTheDocument();

    const botonSolicitar = screen.getByRole("button", { name: "Solicitar taxi" });
    await waitFor(() => expect(botonSolicitar).toBeEnabled());
    await user.click(botonSolicitar);

    await waitFor(() => {
      const post = llamadas.find((c) => c.method === "POST" && c.path === "/viajes");
      expect(post?.body).toMatchObject({ destino_lat: -0.2, destino_lon: -78.5, destino_direccion: "Casa color melón" });
    });
  });
});
