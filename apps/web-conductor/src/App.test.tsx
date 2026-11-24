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
    // `subirArchivo` (ronda de foto de perfil / reporte de falla) manda
    // FormData, no JSON -- JSON.parse reventaría sobre eso.
    const bodyEsJson = typeof init?.body === "string";
    llamadas.push({ method, path, body: bodyEsJson ? JSON.parse(init!.body as string) : undefined });

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
    // Ruta óptima (CU-O05/O06/O07 paso 4, ver rutas.ts) — fetch de fondo
    // disparado por el useEffect de PantallaTurno en cuanto hay posición
    // propia + un tramo activo (recogida u oferta). Respuesta mínima
    // realista (mismo shape que EstimacionRutaOut del backend).
    if (method === "GET" && path.startsWith("/viajes/estimacion-ruta")) {
      return responder(200, {
        ruta: [
          [-0.18, -78.46],
          [-0.2, -78.5],
        ],
        distancia_km: 3.1,
        duracion_min: 8,
        origen_directions: true,
      });
    }
    // Campana de notificaciones (Sección 4.2), montada globalmente en el
    // header de AppShell -- fetch de fondo en cada test.
    if (method === "GET" && path.startsWith("/notificaciones/mias")) {
      return responder(200, { items: [], total: 0, no_leidas: 0 });
    }
    // Ronda de foto de perfil: AuthProvider lee /perfil una vez al iniciar
    // sesión para poblar el avatar del header -- fetch de fondo en cada
    // test, sin relación con el foco de la mayoría de ellos. Coincidencia
    // EXACTA (no startsWith) para no tragarse /perfil/sesiones.
    if (method === "GET" && path === "/perfil") {
      return responder(200, { foto_url: null });
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

  it("al cancelar un viaje asignado, exige elegir un motivo antes de confirmar (CU-O07 A3)", async () => {
    const user = await iniciarTurnoConOferta();
    await screen.findByText(/Nuevo viaje/);

    mockFetch([
      { method: "POST", path: "/viajes/oferta/responder", body: { estado: "ASIGNADO" } },
      { method: "GET", path: "/viajes/conductor/activo", body: VIAJE_ASIGNADO_FIXTURE },
    ]);
    await user.click(screen.getByRole("button", { name: "Aceptar" }));
    await screen.findByText("Viaje asignado");

    const { llamadas } = mockFetch([
      {
        method: "GET",
        path: "/catalogos/motivos",
        body: [{ id: "m1", nombre: "Vehículo averiado" }, { id: "m2", nombre: "Cambio de planes" }],
      },
      { method: "POST", path: "/viajes/conductor/cancelar", body: { estado: "SOLICITADO" } },
    ]);

    await user.click(screen.getByRole("button", { name: "Cancelar viaje" }));

    const select = await screen.findByLabelText("Motivo de la cancelación");
    const botonConfirmar = screen.getByRole("button", { name: "Confirmar cancelación" });
    expect(botonConfirmar).toBeDisabled();

    await user.selectOptions(select, "Vehículo averiado");
    expect(botonConfirmar).toBeEnabled();
    await user.click(botonConfirmar);

    await waitFor(() => {
      const cancelacion = llamadas.find((c) => c.path === "/viajes/conductor/cancelar");
      expect(cancelacion?.body).toEqual({ motivo: "Vehículo averiado" });
    });
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

describe("web-conductor — foto de perfil (ronda de foto de perfil + siembra de 26 usuarios)", () => {
  it("sube una foto nueva desde Ajustes, sin pedir contraseña, y la refleja en el header", async () => {
    const prefsBase = {
      tema: "claro",
      densidad_tablas: "comoda",
      notificaciones_push: {},
      sonido_oferta: true,
      vibracion_oferta: true,
      recordatorio_turno_hora: null,
    };
    const archivoSubido = {
      id: "archivo-foto-1",
      nombre_original: "foto.jpg",
      content_type: "image/jpeg",
      tamano_bytes: 3,
      contexto: "foto_perfil",
      propietario_id: "conductor-test-1",
      ts_creacion: new Date().toISOString(),
    };
    const { llamadas } = mockFetch([
      { method: "GET", path: "/viajes/conductor/activo", body: null },
      { method: "GET", path: "/preferencias", body: prefsBase },
      { method: "POST", path: "/archivos", body: archivoSubido },
      { method: "PATCH", path: "/perfil/foto", body: { foto_url: "archivo-foto-1" } },
    ]);
    const user = userEvent.setup();

    renderApp();
    // Fase 3 del Sistema Riel: Ajustes ya no está en una barra lateral
    // siempre visible -- vive detrás de la parada "Más" del riel inferior.
    await user.click(await screen.findByRole("button", { name: "Más" }));
    await user.click(await screen.findByRole("button", { name: "Ajustes" }));

    const input = await screen.findByLabelText("Cambiar foto");
    const archivo = new File(["contenido-de-prueba"], "foto.jpg", { type: "image/jpeg" });
    await user.upload(input, archivo);

    await waitFor(() => {
      const subida = llamadas.find((c) => c.method === "POST" && c.path === "/archivos");
      expect(subida).toBeDefined();
      const patch = llamadas.find((c) => c.method === "PATCH" && c.path === "/perfil/foto");
      expect(patch?.body).toEqual({ archivo_id: "archivo-foto-1" });
    });

    // No se pidió contraseña en ningún momento -- endpoint separado de
    // "Mi perfil" (decisión D1 no aplica acá, ver AjustesPropios.tsx).
    expect(screen.queryByLabelText("Contraseña actual (para confirmar el cambio)")).not.toBeInTheDocument();
  });
});

describe("web-conductor — Ajustes / preferencias de turno (Sección 2.3 de ux_complementaria.md)", () => {
  it("desactiva el sonido de nueva oferta", async () => {
    const prefsBase = {
      tema: "claro",
      densidad_tablas: "comoda",
      notificaciones_push: {},
      sonido_oferta: true,
      vibracion_oferta: true,
      recordatorio_turno_hora: null,
    };
    const { llamadas } = mockFetch([
      { method: "GET", path: "/viajes/conductor/activo", body: null },
      { method: "GET", path: "/preferencias", body: prefsBase },
      { method: "PATCH", path: "/preferencias", body: { ...prefsBase, sonido_oferta: false } },
    ]);
    const user = userEvent.setup();

    renderApp();
    // Fase 3 del Sistema Riel: Ajustes ya no está en una barra lateral
    // siempre visible -- vive detrás de la parada "Más" del riel inferior.
    await user.click(await screen.findByRole("button", { name: "Más" }));
    await user.click(await screen.findByRole("button", { name: "Ajustes" }));

    const checkboxSonido = await screen.findByLabelText("Sonido al llegar una nueva oferta");
    await user.click(checkboxSonido);

    await waitFor(() => {
      const patch = llamadas.find((c) => c.method === "PATCH" && c.path === "/preferencias");
      expect(patch?.body).toEqual({ sonido_oferta: false });
    });
  });
});

describe("web-conductor — Mi vehículo (ficha de mantenimiento del propio vehículo)", () => {
  const FICHA_FIXTURE = {
    id: "v-test-1",
    placa: "ABC-1234",
    marca: "Toyota",
    modelo: "Corolla",
    estado_habilitacion: "HABILITADO",
    km_acumulado: 4200,
    fecha_ultima_intervencion: "2026-07-01T00:00:00Z",
    km_ultima_intervencion: 4000,
    proxima_km_preventivo: 9000,
    le_toca_preventivo: false,
    umbral_km_preventivo: 5000,
  };

  it("muestra el kilometraje acumulado y la próxima preventiva desde la navegación", async () => {
    const { llamadas } = mockFetch([
      { method: "GET", path: "/viajes/conductor/activo", body: null },
      { method: "GET", path: "/mantenimiento/vehiculos/mio/ficha", body: FICHA_FIXTURE },
    ]);
    const user = userEvent.setup();

    renderApp();
    // Fase 3 del Sistema Riel: "Mi vehículo" vive detrás de la parada "Más"
    // del riel inferior, junto a "Fallas del vehículo"/"Mis documentos".
    await user.click(await screen.findByRole("button", { name: "Más" }));
    await user.click(await screen.findByRole("button", { name: "Mi vehículo" }));

    expect(await screen.findByText(/4[.,]200 km/)).toBeInTheDocument();
    expect(screen.getByText(/9[.,]000 km/)).toBeInTheDocument();
    expect(
      llamadas.some((c) => c.method === "GET" && c.path === "/mantenimiento/vehiculos/mio/ficha"),
    ).toBe(true);
  });

  it("muestra un aviso claro cuando el conductor no tiene ningún vehículo asignado", async () => {
    mockFetch([
      { method: "GET", path: "/viajes/conductor/activo", body: null },
      {
        method: "GET",
        path: "/mantenimiento/vehiculos/mio/ficha",
        status: 404,
        body: { code: "VEHICULO_CONDUCTOR_NO_ASIGNADO", message: "No tenés un vehículo asignado" },
      },
    ]);
    const user = userEvent.setup();

    renderApp();
    await user.click(await screen.findByRole("button", { name: "Más" }));
    await user.click(await screen.findByRole("button", { name: "Mi vehículo" }));

    expect(await screen.findByText(/Todavía no tenés un vehículo asignado/)).toBeInTheDocument();
  });
});
