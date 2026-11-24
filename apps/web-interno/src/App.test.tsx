// Red de seguridad para los flujos críticos de web-interno ya verificados
// manualmente en navegador: el patrón WorkPanel (búsqueda + paginación +
// detalle) en Solicitudes, y el flujo de aprobar/rechazar una solicitud de
// conductor (CU-O01). No busca cobertura completa — solo que estos caminos
// no se rompan en silencio con cambios futuros. Solicitudes es la pantalla
// elegida porque cubre ambos requisitos a la vez: es el mismo patrón que
// Mantenimiento/Finanzas/Cumplimiento, y es donde vive aprobar/rechazar.
import { AuthProvider } from "@urbanflet/shared-ui";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

function makeFakeAccessToken(payload: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: "none", typ: "JWT" }));
  const body = btoa(JSON.stringify(payload));
  return `${header}.${body}.signature`;
}

function loginComoAdminCaptacion(usuarioId = "admin-captacion-test-1") {
  localStorage.setItem(
    "urbanflet.access_token",
    makeFakeAccessToken({ sub: usuarioId, roles: ["admin_captacion"] }),
  );
  localStorage.setItem("urbanflet.refresh_token", "refresh-token-test");
}

function loginComoAdminSistema(usuarioId = "admin-sistema-test-1") {
  localStorage.setItem(
    "urbanflet.access_token",
    makeFakeAccessToken({ sub: usuarioId, roles: ["admin_sistema"] }),
  );
  localStorage.setItem("urbanflet.refresh_token", "refresh-token-test");
}

interface SolicitudFixture {
  id: string;
  usuario_id: string;
  usuario_nombre: string | null;
  cedula: string;
  licencia_numero: string;
  vehiculo: { placa: string; marca: string; modelo: string; anio: number; color: string; capacidad: number };
  estado: string;
  fecha_envio: string | null;
  fecha_decision: string | null;
  revision_reforzada: boolean;
  motivo_rechazo: string | null;
  // Gestión documental en la postulación: `SolicitudOut.documentos` siempre
  // viaja (lista vacía si la solicitud es anterior a esa ronda) -- el mock lo
  // refleja para que el test ejercite el render real del bloque de revisión.
  documentos: {
    tipo: string;
    propietario_tipo: string;
    archivo_id: string;
    fecha_emision: string | null;
    fecha_vencimiento: string | null;
  }[];
}

function crearSolicitud(overrides: Partial<SolicitudFixture> = {}): SolicitudFixture {
  return {
    id: "sol-1",
    usuario_id: "user-1",
    usuario_nombre: "Juan Pérez",
    cedula: "1712345678",
    licencia_numero: "LIC-0001",
    vehiculo: { placa: "PBA-1234", marca: "Chevrolet", modelo: "Sail", anio: 2020, color: "Blanco", capacidad: 4 },
    estado: "EN_VERIFICACION",
    fecha_envio: "2026-07-20T10:00:00Z",
    fecha_decision: null,
    revision_reforzada: false,
    motivo_rechazo: null,
    documentos: [
      {
        tipo: "LICENCIA_CONDUCIR",
        propietario_tipo: "CONDUCTOR",
        archivo_id: "arch-lic-1",
        fecha_emision: null,
        fecha_vencimiento: "2030-01-31",
      },
    ],
    ...overrides,
  };
}

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
    // Default para la campana de notificaciones (Sección 4.2), montada
    // globalmente en el header de AppShell -- dispara su propio fetch de
    // fondo en cada test, sin relación con el foco de la mayoría de ellos.
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
    // Ronda de personalización: `Panel()` lee las secciones favoritas del
    // sidebar una vez al montar -- otro fetch de fondo global, sin relación
    // con el foco de la mayoría de los tests. Sin favoritos por defecto: el
    // sidebar queda exactamente como antes de esta ronda.
    if (method === "GET" && path === "/preferencias") {
      return responder(200, { secciones_favoritas: [] });
    }
    throw new Error(`Llamada a fetch no esperada en este test: ${method} ${path}`);
  }) as unknown as typeof fetch;

  return { llamadas };
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
  loginComoAdminCaptacion();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("web-interno — patrón WorkPanel (búsqueda + paginación + detalle) en Solicitudes", () => {
  it("busca por cédula, pide la página siguiente y abre el detalle de una fila", async () => {
    const listaInicial = {
      items: [crearSolicitud(), crearSolicitud({ id: "sol-2", cedula: "0912345678", usuario_nombre: "Ana Ruiz" })],
      total: 25,
    };
    const { llamadas } = mockFetch([
      { method: "GET", path: "/captacion/solicitudes", body: listaInicial },
      { method: "GET", path: "/captacion/solicitudes", body: { items: [crearSolicitud()], total: 25 } },
      { method: "GET", path: "/captacion/solicitudes", body: { items: [crearSolicitud()], total: 1 } },
    ]);
    const user = userEvent.setup();

    renderApp();

    expect(await screen.findByText("0912345678")).toBeInTheDocument();

    // Paginación: "Siguiente" debe pedir offset=20 (pageSize por defecto).
    await user.click(await screen.findByRole("button", { name: "Siguiente" }));
    await waitFor(() => {
      const segunda = llamadas.filter((c) => c.path.startsWith("/captacion/solicitudes"))[1];
      expect(segunda.path).toContain("offset=20");
    });

    // Búsqueda por cédula: dispara un nuevo fetch con el filtro aplicado.
    await user.type(screen.getByLabelText("Cédula"), "1712345678");
    await user.click(screen.getByRole("button", { name: "Buscar" }));
    await waitFor(() => {
      const tercera = llamadas.filter((c) => c.path.startsWith("/captacion/solicitudes"))[2];
      expect(tercera.path).toContain("cedula=1712345678");
    });

    // Detalle: clic en "Ver" abre el panel con los datos de esa solicitud.
    const botonesVer = await screen.findAllByRole("button", { name: "Ver" });
    await user.click(botonesVer[0]);
    expect(await screen.findByText("Solicitud — cédula 1712345678")).toBeInTheDocument();
  });
});

describe("web-interno — aprobar/rechazar solicitud de conductor (CU-O01)", () => {
  it("aprueba una solicitud EN_VERIFICACION sin requerir motivo", async () => {
    const solicitud = crearSolicitud();
    const { llamadas } = mockFetch([
      { method: "GET", path: "/captacion/solicitudes", body: { items: [solicitud], total: 1 } },
      { method: "POST", path: `/captacion/solicitudes/${solicitud.id}/decision`, body: null },
      { method: "GET", path: "/captacion/solicitudes", body: { items: [], total: 0 } },
    ]);
    const user = userEvent.setup();

    renderApp();
    await user.click(await screen.findByRole("button", { name: "Ver" }));

    // Gestión documental en la postulación (Fase 2): quien decide ve los
    // documentos enviados y su caducidad ANTES de aprobar -- antes de esa
    // ronda esta pantalla no mostraba ninguno.
    expect(await screen.findByText("Documentos enviados")).toBeInTheDocument();
    // Bitácora de revisión (hallazgo #4): el tipo se muestra con su nombre
    // legible, no el enum crudo -- y la fecha con el mismo formato local que
    // el resto del sistema (se compara contra el resultado real de
    // `toLocaleDateString()`, no un string fijo, para no depender del
    // locale del entorno donde corra el test).
    expect(screen.getByText("Licencia de conducir")).toBeInTheDocument();
    expect(screen.getByText(`Caduca: ${new Date("2030-01-31").toLocaleDateString()}`)).toBeInTheDocument();
    expect(screen.getByText("Vigente")).toBeInTheDocument();

    const botonAceptar = await screen.findByRole("button", { name: "Aceptar decisión" });
    expect(botonAceptar).toBeEnabled(); // "Aprobar" es la decisión por defecto, no pide motivo.
    await user.click(botonAceptar);

    await waitFor(() => {
      const decision = llamadas.find((c) => c.path === `/captacion/solicitudes/${solicitud.id}/decision`);
      expect(decision?.body).toEqual({ decision: "APROBADA", motivo: undefined });
    });
  });

  it("rechazar exige motivo antes de habilitar 'Aceptar decisión'", async () => {
    const solicitud = crearSolicitud();
    const { llamadas } = mockFetch([
      { method: "GET", path: "/captacion/solicitudes", body: { items: [solicitud], total: 1 } },
      { method: "POST", path: `/captacion/solicitudes/${solicitud.id}/decision`, body: null },
      { method: "GET", path: "/captacion/solicitudes", body: { items: [], total: 0 } },
    ]);
    const user = userEvent.setup();

    renderApp();
    await user.click(await screen.findByRole("button", { name: "Ver" }));

    await user.selectOptions(await screen.findByLabelText("Decisión"), "Rechazar");
    const botonAceptar = screen.getByRole("button", { name: "Aceptar decisión" });
    expect(botonAceptar).toBeDisabled();

    await user.type(screen.getByLabelText("Motivo (obligatorio)"), "Documentación incompleta");
    expect(botonAceptar).toBeEnabled();
    await user.click(botonAceptar);

    await waitFor(() => {
      const decision = llamadas.find((c) => c.path === `/captacion/solicitudes/${solicitud.id}/decision`);
      expect(decision?.body).toEqual({ decision: "RECHAZADA", motivo: "Documentación incompleta" });
    });
  });
});

interface UsuarioFixture {
  id: string;
  nombre: string;
  telefono: string | null;
  email: string | null;
  roles: string[];
  estado: string;
  fecha_registro: string;
  forzar_cambio_password: boolean;
  motivo_suspension: string | null;
  motivo_baja: string | null;
}

function crearUsuario(overrides: Partial<UsuarioFixture> = {}): UsuarioFixture {
  return {
    id: "user-staff-1",
    nombre: "Jefe De Prueba",
    telefono: "+593900000001",
    email: null,
    roles: ["jefe_mantenimiento"],
    estado: "ACTIVO",
    fecha_registro: "2026-07-20T10:00:00Z",
    forzar_cambio_password: false,
    motivo_suspension: null,
    motivo_baja: null,
    ...overrides,
  };
}

describe("web-interno — Administración → Usuarios (Módulo 1 de admin_sistema)", () => {
  beforeEach(() => {
    localStorage.clear();
    loginComoAdminSistema();
  });

  it("busca cuentas, abre el detalle y suspende con motivo obligatorio", async () => {
    const usuario = crearUsuario();
    const { llamadas } = mockFetch([
      { method: "GET", path: "/usuarios", body: { items: [usuario], total: 1 } },
      { method: "GET", path: "/usuarios/user-staff-1/accesos", body: [] },
      { method: "GET", path: "/usuarios/user-staff-1/sesiones", body: [] },
      { method: "POST", path: "/usuarios/user-staff-1/suspender", body: { ...usuario, estado: "SUSPENDIDO", motivo_suspension: "Cuenta comprometida" } },
      { method: "GET", path: "/usuarios", body: { items: [{ ...usuario, estado: "SUSPENDIDO" }], total: 1 } },
    ]);
    const user = userEvent.setup();

    render(
      <AuthProvider>
        <App />
      </AuthProvider>,
    );

    expect(await screen.findByText("Jefe De Prueba")).toBeInTheDocument();

    await user.click(await screen.findByRole("button", { name: "Ver" }));
    expect(await screen.findByText("Cuenta — Jefe De Prueba")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Suspender" }));
    const botonConfirmar = screen.getByRole("button", { name: "Confirmar suspensión" });
    expect(botonConfirmar).toBeDisabled();

    await user.type(screen.getByLabelText("Motivo (obligatorio)"), "Cuenta comprometida");
    expect(botonConfirmar).toBeEnabled();
    await user.click(botonConfirmar);

    await waitFor(() => {
      const suspender = llamadas.find((c) => c.path === "/usuarios/user-staff-1/suspender");
      expect(suspender?.body).toEqual({ motivo: "Cuenta comprometida" });
    });
  });

  it("crea una cuenta nueva de personal interno con roles seleccionados", async () => {
    const { llamadas } = mockFetch([
      { method: "GET", path: "/usuarios", body: { items: [], total: 0 } },
      { method: "POST", path: "/usuarios", body: crearUsuario({ roles: ["coordinador_flota"] }) },
      { method: "GET", path: "/usuarios", body: { items: [crearUsuario({ roles: ["coordinador_flota"] })], total: 1 } },
    ]);
    const user = userEvent.setup();

    render(
      <AuthProvider>
        <App />
      </AuthProvider>,
    );

    await user.click(await screen.findByRole("button", { name: "Nuevo" }));
    await user.type(await screen.findByLabelText("Nombre"), "Nueva Coordinadora");
    await user.type(screen.getByLabelText("Teléfono"), "+593900000002");
    // Por defecto la contraseña se genera sola -- se desmarca para probar
    // el camino de contraseña manual con confirmación.
    await user.click(screen.getByLabelText("Generar contraseña automáticamente (recomendado)"));
    await user.type(screen.getByLabelText("Contraseña inicial"), "clave-larga-123");
    await user.type(screen.getByLabelText("Confirmar contraseña"), "clave-larga-123");
    await user.click(screen.getByLabelText("Coordinador de Flota"));

    await user.click(screen.getByRole("button", { name: "Crear cuenta" }));

    await waitFor(() => {
      const creacion = llamadas.find((c) => c.method === "POST" && c.path === "/usuarios");
      expect(creacion?.body).toEqual({
        nombre: "Nueva Coordinadora",
        telefono: "+593900000002",
        email: undefined,
        password: "clave-larga-123",
        roles: ["coordinador_flota"],
      });
    });
  });

  it("genera la contraseña automáticamente por defecto y la muestra una sola vez", async () => {
    mockFetch([
      { method: "GET", path: "/usuarios", body: { items: [], total: 0 } },
      {
        method: "POST",
        path: "/usuarios",
        body: { ...crearUsuario({ roles: ["coordinador_flota"] }), password_generada: "Ab3cD4eF5gH6" },
      },
      { method: "GET", path: "/usuarios", body: { items: [crearUsuario({ roles: ["coordinador_flota"] })], total: 1 } },
    ]);
    const user = userEvent.setup();

    render(
      <AuthProvider>
        <App />
      </AuthProvider>,
    );

    await user.click(await screen.findByRole("button", { name: "Nuevo" }));
    await user.type(await screen.findByLabelText("Nombre"), "Otra Coordinadora");
    await user.type(screen.getByLabelText("Teléfono"), "+593900000003");
    // El checkbox queda marcado por defecto -- no hace falta tocarlo.
    await user.click(screen.getByLabelText("Coordinador de Flota"));
    await user.click(screen.getByRole("button", { name: "Crear cuenta" }));

    expect(await screen.findByLabelText("Contraseña generada")).toHaveValue("Ab3cD4eF5gH6");
    expect(screen.getByText(/se muestra una sola vez/)).toBeInTheDocument();
  });

  it("restablece la contraseña de una cuenta existente y la muestra una sola vez", async () => {
    const staff = crearUsuario();
    mockFetch([
      { method: "GET", path: "/usuarios", body: { items: [staff], total: 1 } },
      { method: "GET", path: "/usuarios/user-staff-1/accesos", body: [] },
      { method: "GET", path: "/usuarios/user-staff-1/sesiones", body: [] },
      { method: "POST", path: "/usuarios/user-staff-1/restablecer-password", body: { password_generada: "Zx9yW8vU7t" } },
    ]);
    const user = userEvent.setup();

    render(
      <AuthProvider>
        <App />
      </AuthProvider>,
    );

    await user.click(await screen.findByRole("button", { name: "Ver" }));
    await user.click(await screen.findByRole("button", { name: "Restablecer contraseña" }));

    expect(await screen.findByLabelText("Contraseña nueva")).toHaveValue("Zx9yW8vU7t");
  });

  it("permite filtrar y gestionar una cuenta de conductor, pero no editar sus roles (punto #7)", async () => {
    const conductor = crearUsuario({ id: "user-cond-1", nombre: "Conductor De Prueba", roles: ["conductor"] });
    const { llamadas } = mockFetch([
      { method: "GET", path: "/usuarios", body: { items: [], total: 0 } },
      { method: "GET", path: "/usuarios?rol=conductor", body: { items: [conductor], total: 1 } },
      { method: "GET", path: "/usuarios/user-cond-1/accesos", body: [] },
      { method: "GET", path: "/usuarios/user-cond-1/sesiones", body: [] },
      { method: "POST", path: "/usuarios/user-cond-1/suspender", body: { ...conductor, estado: "SUSPENDIDO", motivo_suspension: "Reporte de mal comportamiento" } },
      { method: "GET", path: "/usuarios?rol=conductor", body: { items: [{ ...conductor, estado: "SUSPENDIDO" }], total: 1 } },
    ]);
    const user = userEvent.setup();

    render(
      <AuthProvider>
        <App />
      </AuthProvider>,
    );

    const filtroRol = await screen.findByLabelText("Rol");
    await user.selectOptions(filtroRol, "conductor");

    expect(await screen.findByText("Conductor De Prueba")).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "Ver" }));

    // Los roles se muestran pero no son editables para una cuenta externa.
    const notaNoEditable = await screen.findByTitle(/No editable: pasajero\/conductor/);
    expect(notaNoEditable).toHaveTextContent("conductor");
    expect(screen.queryByText("Guardar roles")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Administrador del Sistema")).not.toBeInTheDocument();

    // Sí se puede suspender, igual que una cuenta de personal interno.
    await user.click(screen.getByRole("button", { name: "Suspender" }));
    await user.type(screen.getByLabelText("Motivo (obligatorio)"), "Reporte de mal comportamiento");
    await user.click(screen.getByRole("button", { name: "Confirmar suspensión" }));

    await waitFor(() => {
      const suspender = llamadas.find((c) => c.path === "/usuarios/user-cond-1/suspender");
      expect(suspender?.body).toEqual({ motivo: "Reporte de mal comportamiento" });
    });
  });
});

interface FlagFixture {
  id: string;
  nombre: string;
  activo: boolean;
  porcentaje: number | null;
  roles: string[];
  creado_en: string;
  actualizado_en: string;
}

function crearFlag(overrides: Partial<FlagFixture> = {}): FlagFixture {
  return {
    id: "flag-1",
    nombre: "pago_electronico",
    activo: false,
    porcentaje: null,
    roles: [],
    creado_en: "2026-07-20T10:00:00Z",
    actualizado_en: "2026-07-20T10:00:00Z",
    ...overrides,
  };
}

describe("web-interno — Administración → Funcionalidades (Módulo 2.2 de admin_sistema)", () => {
  beforeEach(() => {
    localStorage.clear();
    loginComoAdminSistema();
  });

  it("lista flags y activa uno existente con porcentaje", async () => {
    const flag = crearFlag();
    const { llamadas } = mockFetch([
      { method: "GET", path: "/usuarios", body: { items: [], total: 0 } },
      { method: "GET", path: "/configuracion/flags", body: [flag] },
      { method: "PATCH", path: "/configuracion/flags/pago_electronico", body: { ...flag, activo: true, porcentaje: 25 } },
    ]);
    const user = userEvent.setup();

    render(
      <AuthProvider>
        <App />
      </AuthProvider>,
    );

    await user.click(await screen.findByRole("button", { name: "Funcionalidades" }));
    expect(await screen.findByText("pago_electronico")).toBeInTheDocument();

    await user.click(await screen.findByRole("button", { name: "Ver" }));
    await user.click(await screen.findByLabelText("Activo"));
    await user.type(screen.getByLabelText("Porcentaje (vacío = 100%)"), "25");
    await user.click(screen.getByRole("button", { name: "Guardar cambios" }));

    await waitFor(() => {
      const patch = llamadas.find((c) => c.method === "PATCH" && c.path === "/configuracion/flags/pago_electronico");
      expect(patch?.body).toEqual({ activo: true, porcentaje: 25, roles: [] });
    });
  });
});

describe("web-interno — Administración → Auditoría (Módulo 6.1 de admin_sistema)", () => {
  beforeEach(() => {
    localStorage.clear();
    loginComoAdminSistema();
  });

  it("carga la bitácora pre-filtrada a acciones administrativas y muestra el antes/después", async () => {
    const evento = {
      evento_id: 1,
      ts: "2026-08-05T10:00:00Z",
      actor_id: "admin-1",
      rol: "admin_sistema",
      accion: "ROL_MODIFICACION",
      entidad: "usuarios",
      entidad_id: "u-2",
      resultado: "OK",
      datos_previos: { roles: ["jefe_mantenimiento"] },
      datos_posteriores: { roles: ["jefe_mantenimiento", "coordinador_flota"] },
    };
    const { llamadas } = mockFetch([
      { method: "GET", path: "/usuarios", body: { items: [], total: 0 } },
      { method: "GET", path: "/auditoria/acciones-administrativas", body: ["USUARIO_CREACION", "ROL_MODIFICACION", "PARAMETRO_SISTEMA_CAMBIO"] },
      { method: "GET", path: "/auditoria/eventos", body: { items: [evento], total: 1, pagina: 1, tamanio_pagina: 100 } },
    ]);
    const user = userEvent.setup();

    render(
      <AuthProvider>
        <App />
      </AuthProvider>,
    );

    await user.click(await screen.findByRole("button", { name: "Auditoría" }));
    expect(await screen.findByRole("cell", { name: "ROL_MODIFICACION" })).toBeInTheDocument();

    const llamadaEventos = llamadas.find((c) => c.path.startsWith("/auditoria/eventos"));
    expect(llamadaEventos?.path).toContain("accion=USUARIO_CREACION");
    expect(llamadaEventos?.path).toContain("accion=PARAMETRO_SISTEMA_CAMBIO");

    await user.click(await screen.findByRole("button", { name: "Ver antes/después" }));
    // "jefe_mantenimiento" aparece en ambos bloques (antes Y después); solo
    // "coordinador_flota" es exclusivo del bloque "después".
    expect(await screen.findAllByText(/"jefe_mantenimiento"/)).toHaveLength(2);
    expect(screen.getByText(/"coordinador_flota"/)).toBeInTheDocument();
  });
});

describe("web-interno — Administración → Catálogos (Módulo 3 de admin_sistema)", () => {
  beforeEach(() => {
    localStorage.clear();
    loginComoAdminSistema();
  });

  it("crea un tipo de documento nuevo desde la pestaña Tipos de documento", async () => {
    const { llamadas } = mockFetch([
      { method: "GET", path: "/usuarios", body: { items: [], total: 0 } },
      { method: "GET", path: "/catalogos/tipos-documento", body: [] },
      {
        method: "POST",
        path: "/catalogos/tipos-documento",
        body: { id: "tipo-1", nombre: "Matrícula", descripcion: "", aplica_a: "vehiculo", activo: true },
      },
      { method: "GET", path: "/catalogos/tipos-documento", body: [{ id: "tipo-1", nombre: "Matrícula", descripcion: "", aplica_a: "vehiculo", activo: true }] },
    ]);
    const user = userEvent.setup();

    render(
      <AuthProvider>
        <App />
      </AuthProvider>,
    );

    await user.click(await screen.findByRole("button", { name: "Catálogos" }));
    await user.click(await screen.findByRole("button", { name: "Tipos de documento" }));

    await user.click(await screen.findByRole("button", { name: "Nuevo" }));
    await user.type(await screen.findByLabelText("Nombre"), "Matrícula");
    await user.selectOptions(screen.getByLabelText("Aplica a"), "Vehículo");
    await user.click(screen.getByRole("button", { name: "Guardar" }));

    await waitFor(() => {
      const creacion = llamadas.find((c) => c.method === "POST" && c.path === "/catalogos/tipos-documento");
      expect(creacion?.body).toEqual({ nombre: "Matrícula", descripcion: "", aplica_a: "vehiculo", activo: true });
    });
  });
});

describe("web-interno — Administración → Versión (Módulo 8.1 de admin_sistema)", () => {
  beforeEach(() => {
    localStorage.clear();
    loginComoAdminSistema();
  });

  it("muestra la versión vigente y registra un despliegue nuevo", async () => {
    const version = { backend: "0.1.0", web_pasajero: "0.1.0", web_conductor: "0.1.0", web_interno: "0.1.0" };
    const { llamadas } = mockFetch([
      { method: "GET", path: "/usuarios", body: { items: [], total: 0 } },
      { method: "GET", path: "/sistema/version", body: version },
      { method: "GET", path: "/sistema/despliegues", body: [] },
      {
        method: "POST",
        path: "/sistema/despliegues",
        body: { id: "d-1", componente: "backend", version: "0.2.0", notas: "", desplegado_en: "2026-08-05T10:00:00Z", desplegado_por: "admin-1" },
      },
      { method: "GET", path: "/sistema/despliegues", body: [{ id: "d-1", componente: "backend", version: "0.2.0", notas: "", desplegado_en: "2026-08-05T10:00:00Z", desplegado_por: "admin-1" }] },
    ]);
    const user = userEvent.setup();

    render(
      <AuthProvider>
        <App />
      </AuthProvider>,
    );

    await user.click(await screen.findByRole("button", { name: "Versión" }));
    expect(await screen.findAllByText("0.1.0")).toHaveLength(4);

    await user.type(await screen.findByLabelText("Versión"), "0.2.0");
    await user.click(screen.getByRole("button", { name: "Registrar despliegue" }));

    await waitFor(() => {
      const creacion = llamadas.find((c) => c.method === "POST" && c.path === "/sistema/despliegues");
      expect(creacion?.body).toEqual({ componente: "backend", version: "0.2.0", notas: "" });
    });
  });
});

describe("web-interno — Administración → Políticas de seguridad (Módulo 6.2 de admin_sistema)", () => {
  beforeEach(() => {
    localStorage.clear();
    loginComoAdminSistema();
  });

  it("carga los valores vigentes y publica un cambio de umbral RBAC", async () => {
    const politica = {
      id: null,
      access_token_minutos: 15,
      refresh_token_dias: 30,
      refresh_umbral_fallos: 3,
      refresh_ventana_minutos: 15,
      rbac_umbral_denegaciones: 5,
      rbac_ventana_minutos: 10,
      rbac_suspension_minutos: 30,
      vigente_desde: null,
      vigente_hasta: null,
    };
    const { llamadas } = mockFetch([
      { method: "GET", path: "/usuarios", body: { items: [], total: 0 } },
      { method: "GET", path: "/seguridad/politica-seguridad", body: politica },
      { method: "POST", path: "/seguridad/politica-seguridad", body: { ...politica, id: "p-1", rbac_umbral_denegaciones: 3 } },
    ]);
    const user = userEvent.setup();

    render(
      <AuthProvider>
        <App />
      </AuthProvider>,
    );

    await user.click(await screen.findByRole("button", { name: "Políticas de seguridad" }));
    const umbral = await screen.findByLabelText("Umbral de denegaciones");
    expect(umbral).toHaveValue(5);
    expect(umbral).toBeDisabled(); // solo-lectura por defecto (punto #4)

    await user.click(screen.getByRole("button", { name: "Editar" }));
    await user.clear(umbral);
    await user.type(umbral, "3");
    await user.click(screen.getByRole("button", { name: "Publicar política" }));

    await waitFor(() => {
      const publicar = llamadas.find((c) => c.method === "POST" && c.path === "/seguridad/politica-seguridad");
      expect(publicar?.body).toMatchObject({ rbac_umbral_denegaciones: 3 });
    });
  });

  it("muestra el mensaje de validación junto al campo cuando el backend rechaza un umbral inválido (repro reportado)", async () => {
    const politica = {
      id: null, access_token_minutos: 15, refresh_token_dias: 30, refresh_umbral_fallos: 3,
      refresh_ventana_minutos: 15, rbac_umbral_denegaciones: 5, rbac_ventana_minutos: 10,
      rbac_suspension_minutos: 30, vigente_desde: null, vigente_hasta: null,
    };
    mockFetch([
      { method: "GET", path: "/usuarios", body: { items: [], total: 0 } },
      { method: "GET", path: "/seguridad/politica-seguridad", body: politica },
      {
        method: "POST", path: "/seguridad/politica-seguridad", status: 422,
        body: {
          code: "VALIDATION_ERROR",
          message: "rbac_umbral_denegaciones: Debe ser mayor o igual a 3",
          errores: [{ campo: "rbac_umbral_denegaciones", mensaje: "Debe ser mayor o igual a 3" }],
        },
      },
    ]);
    const user = userEvent.setup();

    render(
      <AuthProvider>
        <App />
      </AuthProvider>,
    );

    await user.click(await screen.findByRole("button", { name: "Políticas de seguridad" }));
    const umbral = await screen.findByLabelText("Umbral de denegaciones");
    await user.click(screen.getByRole("button", { name: "Editar" }));
    await user.clear(umbral);
    await user.type(umbral, "1");
    await user.click(screen.getByRole("button", { name: "Publicar política" }));

    // El mensaje aparece junto al campo exacto que falló -- no un banner
    // genérico ni un error de consola sin traducir.
    expect(await screen.findByText("Debe ser mayor o igual a 3")).toBeInTheDocument();
  });
});

describe("web-interno — Administración → Configuración de alertas (Módulo 6.3 de admin_sistema)", () => {
  beforeEach(() => {
    localStorage.clear();
    loginComoAdminSistema();
  });

  it("lista las 3 alertas y agrega un destinatario adicional buscándolo por nombre (punto #5)", async () => {
    const alertas = [
      { tipo_alerta: "denegaciones_rbac", canal: "web_push", destinatarios_adicionales: [], activo: true, rol_destinatario_default: "supervisor_cumplimiento", actualizado_en: null },
      { tipo_alerta: "gps_spoofing", canal: "web_push", destinatarios_adicionales: [], activo: true, rol_destinatario_default: "supervisor_cumplimiento", actualizado_en: null },
      { tipo_alerta: "pipeline_fallido", canal: "web_push", destinatarios_adicionales: [], activo: true, rol_destinatario_default: "responsable_plataforma", actualizado_en: null },
    ];
    const backup = { id: "backup-1", nombre: "Backup Cumplimiento", telefono: "+593900000800", email: null, roles: ["supervisor_cumplimiento"] };
    const { llamadas } = mockFetch([
      { method: "GET", path: "/usuarios", body: { items: [], total: 0 } },
      { method: "GET", path: "/notificaciones/alertas-config", body: alertas },
      { method: "GET", path: "/usuarios?texto=Backup", body: { items: [backup], total: 1 } },
      { method: "PATCH", path: "/notificaciones/alertas-config/gps_spoofing", body: { ...alertas[1], destinatarios_adicionales: ["backup-1"] } },
    ]);
    const user = userEvent.setup();

    render(
      <AuthProvider>
        <App />
      </AuthProvider>,
    );

    await user.click(await screen.findByRole("button", { name: "Configuración de alertas" }));
    expect(await screen.findByText("Posible falsificación de ubicación GPS")).toBeInTheDocument();

    const filas = await screen.findAllByRole("button", { name: "Ver" });
    await user.click(filas[1]); // gps_spoofing es la segunda fila

    const buscador = await screen.findByLabelText("Buscar por nombre, teléfono o correo");
    await user.type(buscador, "Backup");
    await user.click(screen.getByRole("button", { name: "Buscar" }));

    expect(await screen.findByText("Backup Cumplimiento")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Agregar" }));
    expect(await screen.findByText("Backup Cumplimiento — supervisor_cumplimiento")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Guardar" }));

    await waitFor(() => {
      const patch = llamadas.find((c) => c.method === "PATCH" && c.path === "/notificaciones/alertas-config/gps_spoofing");
      expect(patch?.body).toEqual({ canal: "web_push", destinatarios_adicionales: ["backup-1"], activo: true });
    });
    // El usuario nunca ve ni escribe el usuario_id crudo.
    expect(screen.queryByText("backup-1")).not.toBeInTheDocument();
  });
});

describe("web-interno — Administración → Integraciones (Módulo 4 de admin_sistema)", () => {
  beforeEach(() => {
    localStorage.clear();
    loginComoAdminSistema();
  });

  it("crea una credencial y muestra el secreto una sola vez", async () => {
    const credencialCreada = {
      id: "cred-1", nombre: "Municipio", alcance: "", vigente_desde: "2026-08-01T00:00:00Z",
      vigente_hasta: null, revocada: false, usos_registrados: 0, secreto: "secreto-de-prueba-largo-123456",
    };
    const { llamadas } = mockFetch([
      { method: "GET", path: "/integraciones/credenciales", body: [] },
      { method: "POST", path: "/integraciones/credenciales", status: 201, body: credencialCreada },
      { method: "GET", path: "/integraciones/credenciales", body: [{ ...credencialCreada, secreto: undefined }] },
    ]);
    const user = userEvent.setup();

    render(
      <AuthProvider>
        <App />
      </AuthProvider>,
    );

    await user.click(await screen.findByRole("button", { name: "Integraciones" }));
    await user.click(await screen.findByRole("button", { name: "Nuevo" }));
    await user.type(await screen.findByLabelText("Nombre"), "Municipio");
    await user.click(screen.getByRole("button", { name: "Crear" }));

    expect(await screen.findByText(/se muestra una sola vez/)).toBeInTheDocument();
    expect(await screen.findByDisplayValue("secreto-de-prueba-largo-123456")).toBeInTheDocument();

    await waitFor(() => {
      const post = llamadas.find((c) => c.method === "POST" && c.path === "/integraciones/credenciales");
      expect(post?.body).toEqual({ nombre: "Municipio", alcance: "" });
    });
  });

  it("rota la key de Google Maps y confirma el efecto inmediato en la lista", async () => {
    const servicios = [
      { nombre: "google_maps", estado: "no_configurado", key_enmascarada: null },
      { nombre: "sms", estado: "no_configurado", key_enmascarada: null },
      { nombre: "s3", estado: "no_configurado", key_enmascarada: null },
    ];
    const serviciosRotados = [
      { nombre: "google_maps", estado: "activo", key_enmascarada: "••••e123" },
      { nombre: "sms", estado: "no_configurado", key_enmascarada: null },
      { nombre: "s3", estado: "no_configurado", key_enmascarada: null },
    ];
    const { llamadas } = mockFetch([
      { method: "GET", path: "/integraciones/credenciales", body: [] },
      { method: "GET", path: "/integraciones/servicios-externos", body: servicios },
      { method: "POST", path: "/integraciones/servicios-externos/google_maps/rotar", body: serviciosRotados[0] },
      { method: "GET", path: "/integraciones/servicios-externos", body: serviciosRotados },
    ]);
    const user = userEvent.setup();

    render(
      <AuthProvider>
        <App />
      </AuthProvider>,
    );

    await user.click(await screen.findByRole("button", { name: "Integraciones" }));
    await user.click(await screen.findByRole("button", { name: "Servicios externos" }));
    await user.click(await screen.findByRole("button", { name: "Rotar clave" }));
    await user.type(await screen.findByLabelText("Nueva clave de API"), "AIzaClaveDePrueba123");
    await user.click(screen.getByRole("button", { name: "Rotar" }));

    expect(await screen.findByText("••••e123")).toBeInTheDocument();
    await waitFor(() => {
      const post = llamadas.find((c) => c.method === "POST" && c.path.includes("/rotar"));
      expect(post?.body).toEqual({ api_key: "AIzaClaveDePrueba123" });
    });
  });
});

describe("web-interno — Administración → Parámetros globales (puntos #2 y #4 de la ronda de usabilidad)", () => {
  beforeEach(() => {
    localStorage.clear();
    loginComoAdminSistema();
  });

  it("aparece bloqueada por defecto, usa selects para idioma/zona horaria, y se edita solo tras pulsar Editar", async () => {
    const config = {
      id: "cfg-1", idioma: "es", zona_horaria: "America/Guayaquil",
      radios_despacho_m: [300, 600, 1000], oferta_expira_segundos: 20,
      vigente_desde: "2026-08-01T00:00:00Z", vigente_hasta: null,
    };
    const { llamadas } = mockFetch([
      { method: "GET", path: "/usuarios", body: { items: [], total: 0 } },
      { method: "GET", path: "/configuracion/parametros-sistema", body: config },
      { method: "POST", path: "/configuracion/parametros-sistema", body: { ...config, idioma: "en" } },
      { method: "GET", path: "/configuracion/parametros-sistema", body: { ...config, idioma: "en" } },
    ]);
    const user = userEvent.setup();

    render(
      <AuthProvider>
        <App />
      </AuthProvider>,
    );

    await user.click(await screen.findByRole("button", { name: "Parámetros globales" }));
    const idioma = (await screen.findByLabelText("Idioma")) as HTMLSelectElement;
    expect(idioma.tagName).toBe("SELECT");
    expect(idioma).toHaveValue("es");
    expect(idioma).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Editar" }));
    expect(idioma).not.toBeDisabled();
    await user.selectOptions(idioma, "en");
    await user.click(screen.getByRole("button", { name: "Publicar configuración" }));

    await waitFor(() => {
      const publicar = llamadas.find((c) => c.method === "POST" && c.path === "/configuracion/parametros-sistema");
      expect(publicar?.body).toMatchObject({ idioma: "en" });
    });
    // Tras guardar, vuelve a modo solo-lectura (punto #4).
    expect(await screen.findByRole("button", { name: "Editar" })).toBeInTheDocument();
  });
});

describe("web-interno — Administración → Monitoreo (Módulo 5 de admin_sistema)", () => {
  beforeEach(() => {
    localStorage.clear();
    loginComoAdminSistema();
  });

  it("muestra el estado de los 5 componentes y actualiza un umbral", async () => {
    const salud = [
      { componente: "backend", disponible: true, latencia_ms: 1.2, estado: "bien" },
      { componente: "mongo", disponible: true, latencia_ms: 3.4, estado: "bien" },
      { componente: "redis", disponible: true, latencia_ms: 0.8, estado: "bien" },
      { componente: "clickhouse", disponible: true, latencia_ms: 12.5, estado: "bien" },
      { componente: "airflow", disponible: false, latencia_ms: null, estado: "critico" },
    ];
    const umbrales = [
      { componente: "backend", latencia_advertencia_ms: 500, latencia_critica_ms: 2000 },
      { componente: "mongo", latencia_advertencia_ms: 200, latencia_critica_ms: 1000 },
      { componente: "redis", latencia_advertencia_ms: 100, latencia_critica_ms: 500 },
      { componente: "clickhouse", latencia_advertencia_ms: 500, latencia_critica_ms: 2000 },
      { componente: "airflow", latencia_advertencia_ms: 1000, latencia_critica_ms: 3000 },
    ];
    const umbralActualizado = { componente: "mongo", latencia_advertencia_ms: 50, latencia_critica_ms: 800 };
    const indicadores = {
      mongo: { disponible: false },
      redis: { disponible: false },
      clickhouse: { disponible: false },
    };
    const { llamadas } = mockFetch([
      { method: "GET", path: "/sistema/salud", body: salud },
      { method: "GET", path: "/sistema/umbrales-monitoreo", body: umbrales },
      { method: "GET", path: "/sistema/indicadores", body: indicadores },
      { method: "GET", path: "/sistema/historial-latencia", body: [] },
      { method: "PUT", path: "/sistema/umbrales-monitoreo/mongo", body: umbralActualizado },
      { method: "GET", path: "/sistema/salud", body: salud },
      { method: "GET", path: "/sistema/umbrales-monitoreo", body: [...umbrales.filter((u) => u.componente !== "mongo"), umbralActualizado] },
      { method: "GET", path: "/sistema/indicadores", body: indicadores },
      { method: "GET", path: "/sistema/historial-latencia", body: [] },
    ]);
    const user = userEvent.setup();

    render(
      <AuthProvider>
        <App />
      </AuthProvider>,
    );

    await user.click(await screen.findByRole("button", { name: "Monitoreo" }));
    expect(await screen.findByText("1.2 ms")).toBeInTheDocument();
    expect((await screen.findAllByText("No disponible")).length).toBeGreaterThan(0);

    const filas = await screen.findAllByRole("button", { name: "Editar" });
    await user.click(filas[1]); // mongo es la segunda fila

    const advertencia = await screen.findByLabelText("Latencia de advertencia (ms)");
    await user.clear(advertencia);
    await user.type(advertencia, "50");
    const critica = await screen.findByLabelText("Latencia crítica (ms)");
    await user.clear(critica);
    await user.type(critica, "800");
    await user.click(screen.getByRole("button", { name: "Guardar" }));

    await waitFor(() => {
      const put = llamadas.find((c) => c.method === "PUT" && c.path === "/sistema/umbrales-monitoreo/mongo");
      expect(put?.body).toEqual({ latencia_advertencia_ms: 50, latencia_critica_ms: 800 });
    });
  });
});

describe("web-interno — Administración → Gobernanza de datos (Módulo 8.2 de admin_sistema)", () => {
  beforeEach(() => {
    localStorage.clear();
    loginComoAdminSistema();
  });

  it("busca un usuario, exige el texto de confirmación exacto y anonimiza", async () => {
    const usuario = {
      id: "user-gob-1", nombre: "Persona Real", telefono: "+593900000801", email: "real@example.com",
      roles: ["jefe_mantenimiento"], estado: "ACTIVO", anonimizado: false,
    };
    const { llamadas } = mockFetch([
      // "Usuarios" es la primera sección de SECCIONES y admin_sistema tiene
      // acceso -- monta por defecto antes de navegar a "Gobernanza de
      // datos" y dispara su propia carga inicial de /usuarios.
      { method: "GET", path: "/usuarios", body: { items: [], total: 0 } },
      { method: "GET", path: "/sistema/politica-retencion", body: [
        { coleccion: "posiciones", descripcion: "GPS", retencion: "7 días (TTL automático real)", fuente: "indice_ttl_real" },
      ] },
      { method: "GET", path: "/usuarios", body: { items: [usuario], total: 1 } },
      { method: "POST", path: "/usuarios/user-gob-1/anonimizar", status: 200, body: { ...usuario, nombre: "Usuario Anonimizado user-gob", telefono: null, email: null, anonimizado: true } },
    ]);
    const user = userEvent.setup();

    render(
      <AuthProvider>
        <App />
      </AuthProvider>,
    );

    await user.click(await screen.findByRole("button", { name: "Gobernanza de datos" }));
    await user.type(await screen.findByLabelText("Nombre, teléfono o correo"), "Persona");
    await user.click(screen.getByRole("button", { name: "Buscar" }));

    await user.click(await screen.findByRole("button", { name: "Anonimizar" }));
    const boton = screen.getByRole("button", { name: "Anonimizar de forma permanente" });
    expect(boton).toBeDisabled();

    const confirmacion = screen.getByLabelText('Escribe "ANONIMIZAR" para confirmar');
    await user.type(confirmacion, "si");
    expect(boton).toBeDisabled();

    await user.clear(confirmacion);
    await user.type(confirmacion, "ANONIMIZAR");
    expect(boton).not.toBeDisabled();
    await user.click(boton);

    await waitFor(() => {
      const post = llamadas.find((c) => c.method === "POST" && c.path === "/usuarios/user-gob-1/anonimizar");
      expect(post?.body).toEqual({ confirmacion: "ANONIMIZAR" });
    });
    expect(screen.queryByText("Persona Real")).not.toBeInTheDocument();
  });
});

describe("web-interno — Administración → Respaldos (Módulo 7 de admin_sistema)", () => {
  beforeEach(() => {
    localStorage.clear();
    loginComoAdminSistema();
  });

  it("dispara un respaldo, lo verifica y lo restaura contra la base de prueba", async () => {
    const respaldoCompletado = {
      id: "resp-1", motor: "mongo", estado: "completado", ts_inicio: "2026-08-06T10:00:00Z",
      ts_fin: "2026-08-06T10:01:00Z", duracion_segundos: 60, tamano_bytes: 2048,
      hash_sha256: "abc123", colecciones: ["usuarios", "viajes"], error_detalle: null,
      disparado_por: "admin-sistema-test-1",
    };
    const enProgreso = (motor: "mongo" | "clickhouse") => ({
      id: `${motor}-en-progreso`, motor, estado: "en_progreso", ts_inicio: "2026-08-06T10:00:00Z",
      ts_fin: null, duracion_segundos: null, tamano_bytes: null, hash_sha256: null,
      colecciones: null, error_detalle: null, disparado_por: "admin-sistema-test-1",
    });
    const { llamadas } = mockFetch([
      // "Usuarios" es la primera sección de SECCIONES y admin_sistema tiene
      // acceso -- monta por defecto antes de navegar a "Respaldos" y
      // dispara su propia carga inicial de /usuarios.
      { method: "GET", path: "/usuarios", body: { items: [], total: 0 } },
      { method: "GET", path: "/respaldos", body: [] },
      { method: "GET", path: "/respaldos/restauraciones", body: [] },
      { method: "POST", path: "/respaldos", status: 202, body: [enProgreso("mongo"), enProgreso("clickhouse")] },
      { method: "GET", path: "/respaldos", body: [respaldoCompletado] },
      { method: "GET", path: "/respaldos/restauraciones", body: [] },
      {
        method: "POST", path: "/respaldos/resp-1/verificar",
        body: { id: "resp-1", integro: true, hash_esperado: "abc123", hash_calculado: "abc123" },
      },
      {
        method: "POST", path: "/respaldos/resp-1/restaurar", status: 202,
        body: {
          id: "rest-1", respaldo_id: "resp-1", motor: "mongo", estado: "en_progreso",
          base_destino: "urbanflet_restore_test", ts_inicio: "2026-08-06T10:05:00Z",
          ts_fin: null, duracion_segundos: null, conteos: null, error_detalle: null,
        },
      },
      { method: "GET", path: "/respaldos", body: [respaldoCompletado] },
      { method: "GET", path: "/respaldos/restauraciones", body: [] },
    ]);
    const user = userEvent.setup();

    render(
      <AuthProvider>
        <App />
      </AuthProvider>,
    );

    await user.click(await screen.findByRole("button", { name: "Respaldos" }));
    await user.click(await screen.findByRole("button", { name: "Nuevo" }));
    await waitFor(() => {
      expect(llamadas.some((c) => c.method === "POST" && c.path === "/respaldos")).toBe(true);
    });

    await user.click(await screen.findByRole("button", { name: "Ver" }));
    await user.click(await screen.findByRole("button", { name: "Verificar integridad" }));
    expect(await screen.findByText("Íntegro: el hash coincide.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Restaurar en base de prueba" }));

    await waitFor(() => {
      expect(llamadas.some((c) => c.method === "POST" && c.path === "/respaldos/resp-1/restaurar")).toBe(true);
    });
  });

  it("gerencia solo ve la pestaña de plan de continuidad, no la de respaldos técnicos", async () => {
    localStorage.setItem(
      "urbanflet.access_token",
      makeFakeAccessToken({ sub: "gerencia-test-1", roles: ["gerencia"] }),
    );
    localStorage.setItem("urbanflet.refresh_token", "refresh-token-test");
    mockFetch([
      { method: "GET", path: "/respaldos/plan-dr", body: [
        { dominio: "operaciones_despacho", rto: "", rpo: "", notas: "", actualizado_en: null, actualizado_por: null },
      ] },
      { method: "GET", path: "/respaldos/simulacros", body: [] },
    ]);

    const user = userEvent.setup();
    render(
      <AuthProvider>
        <App />
      </AuthProvider>,
    );
    await user.click(await screen.findByRole("button", { name: "Respaldos" }));

    // Sin pestañas: aterriza directo en "Plan de continuidad" (lo único que
    // gerencia puede ver) y nunca se ofrece la pestaña "Respaldos" técnicos,
    // que el backend le rechazaría con 403.
    expect(await screen.findByText("RTO / RPO por dominio")).toBeInTheDocument();
    // Sin pestañas (una sola vista) y sin la tabla de respaldos técnicos
    // (su ActionBar "Nuevo" dispara /respaldos, que el backend le rechazaría
    // con 403 a un actor solo-gerencia).
    expect(screen.queryByRole("button", { name: "Plan de continuidad" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Nuevo" })).not.toBeInTheDocument();
  });
});

describe("web-interno — Mi cuenta (Sección 3.1 de ux_complementaria.md)", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("es visible para un rol sin ninguna otra sección asignada, y permite editar el contacto propio", async () => {
    // jefe_mantenimiento tiene "Mantenimiento" como sección propia -- se usa
    // un rol distinto (uno de los 13 con sección real) para probar que "Mi
    // cuenta" convive con el resto de la navegación, no solo que existe
    // cuando no hay nada más.
    localStorage.setItem(
      "urbanflet.access_token",
      makeFakeAccessToken({ sub: "jefe-mant-perfil-1", roles: ["jefe_mantenimiento"] }),
    );
    localStorage.setItem("urbanflet.refresh_token", "refresh-token-test");

    const perfil = {
      id: "jefe-mant-perfil-1",
      nombre: "Jefe Original",
      telefono: "+593900000500",
      email: null,
      roles: ["jefe_mantenimiento"],
      fecha_registro: new Date().toISOString(),
      foto_url: null,
    };
    const { llamadas } = mockFetch([
      { method: "GET", path: "/mantenimiento/ordenes", body: { items: [], total: 0 } },
      // 2 handlers para el mismo GET /perfil: uno lo consume el fetch
      // proactivo de AuthProvider al iniciar sesión (ronda de foto de
      // perfil, puebla el avatar del header), el otro lo consume
      // PerfilPropio al montar su propia tarjeta.
      { method: "GET", path: "/perfil", body: perfil },
      { method: "GET", path: "/perfil", body: perfil },
      { method: "GET", path: "/perfil/sesiones", body: [] },
      { method: "PATCH", path: "/perfil", body: { ...perfil, nombre: "Jefe Actualizado" } },
    ]);
    const user = userEvent.setup();

    render(
      <AuthProvider>
        <App />
      </AuthProvider>,
    );
    await user.click(await screen.findByRole("button", { name: "Mi cuenta" }));

    expect(await screen.findByText("Jefe de Mantenimiento")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Editar" }));
    const nombre = screen.getByLabelText("Nombre");
    await user.clear(nombre);
    await user.type(nombre, "Jefe Actualizado");
    await user.type(screen.getByLabelText("Contraseña actual (para confirmar el cambio)"), "clave-actual");
    await user.click(screen.getByRole("button", { name: "Guardar" }));

    await waitFor(() => {
      const patch = llamadas.find((c) => c.method === "PATCH" && c.path === "/perfil");
      expect(patch?.body).toMatchObject({ nombre: "Jefe Actualizado", password_actual: "clave-actual" });
    });
  });
});

describe("web-interno — Ajustes (Sección 3.2 de ux_complementaria.md)", () => {
  beforeEach(() => {
    localStorage.clear();
    loginComoAdminSistema();
  });

  it("cambia la densidad de tablas y la aplica como variable CSS", async () => {
    const prefsBase = {
      tema: "claro",
      densidad_tablas: "comoda",
      notificaciones_push: {},
      sonido_oferta: true,
      vibracion_oferta: true,
      recordatorio_turno_hora: null,
    };
    mockFetch([
      { method: "GET", path: "/preferencias", body: prefsBase },
      { method: "PATCH", path: "/preferencias", body: { ...prefsBase, densidad_tablas: "compacta" } },
    ]);
    const user = userEvent.setup();

    render(
      <AuthProvider>
        <App />
      </AuthProvider>,
    );
    await user.click(await screen.findByRole("button", { name: "Ajustes" }));

    const selectDensidad = await screen.findByLabelText("Densidad de tablas");
    await user.selectOptions(selectDensidad, "compacta");

    await waitFor(() => {
      expect(document.documentElement.style.getPropertyValue("--table-cell-padding-y")).toBe("3px");
    });
  });
});

describe("web-interno — Historial de viajes (Sección 3.3 de ux_complementaria.md)", () => {
  beforeEach(() => {
    localStorage.clear();
    loginComoAdminSistema();
  });

  function crearViajeHistorial(overrides: Partial<Record<string, unknown>> = {}) {
    return {
      id: "hg-1",
      pasajero_id: "p-1",
      conductor_id: "c-1",
      estado: "FINALIZADO",
      origen_lat: -0.18,
      origen_lon: -78.48,
      origen_direccion: "Av. Amazonas",
      destino_lat: -0.22,
      destino_lon: -78.51,
      destino_direccion: "Terminal Terrestre",
      franja: "DIURNA",
      ts_solicitud: "2026-08-01T10:00:00Z",
      ts_fin: "2026-08-01T10:20:00Z",
      km_recorridos: 4.2,
      tarifa_final: 3.5,
      tarifa_estimada: 3.4,
      motivo_cancelacion: null,
      conductor_nombre: "Luis Vera",
      conductor_calificacion: 4.8,
      vehiculo_placa: "ABC-1234",
      pasajero_nombre: "María",
      pasajero_calificacion: 4.6,
      calificacion_pasajero_a_conductor: { puntaje: 5, comentario: null, ts: "2026-08-01T10:21:00Z" },
      calificacion_conductor_a_pasajero: { puntaje: 5, comentario: null, ts: "2026-08-01T10:21:00Z" },
      ...overrides,
    };
  }

  it("busca por texto, pide la página siguiente y abre el detalle de un viaje", async () => {
    const { llamadas } = mockFetch([
      { method: "GET", path: "/viajes/historial-global", body: { viajes: [crearViajeHistorial()], total: 25 } },
      {
        method: "GET",
        path: "/viajes/historial-global",
        body: { viajes: [crearViajeHistorial({ id: "hg-2" })], total: 25 },
      },
      {
        method: "GET",
        path: "/viajes/historial-global",
        body: { viajes: [crearViajeHistorial({ id: "hg-3", pasajero_nombre: "Ana" })], total: 1 },
      },
    ]);
    const user = userEvent.setup();

    render(
      <AuthProvider>
        <App />
      </AuthProvider>,
    );
    await user.click(await screen.findByRole("button", { name: "Historial de viajes" }));

    expect(await screen.findByText("Luis Vera")).toBeInTheDocument();

    await user.click(await screen.findByRole("button", { name: "Siguiente" }));
    await waitFor(() => {
      const segunda = llamadas.filter((c) => c.path.startsWith("/viajes/historial-global"))[1];
      expect(segunda.path).toContain("pagina=2");
    });

    await user.type(screen.getByLabelText("Nombre de pasajero o conductor"), "Ana");
    await user.click(screen.getByRole("button", { name: "Buscar" }));
    await waitFor(() => {
      const tercera = llamadas.filter((c) => c.path.startsWith("/viajes/historial-global"))[2];
      expect(tercera.path).toContain("texto=Ana");
    });

    const botonesVer = await screen.findAllByRole("button", { name: "Ver" });
    await user.click(botonesVer[0]);
    expect(await screen.findByText("Viaje — hg-3")).toBeInTheDocument();
    expect(screen.getAllByText("Ana").length).toBeGreaterThan(0);
    expect(screen.getAllByText("5★").length).toBe(2);
  });
});
