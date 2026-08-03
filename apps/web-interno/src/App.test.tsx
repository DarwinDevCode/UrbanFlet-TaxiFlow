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

interface SolicitudFixture {
  id: string;
  usuario_id: string;
  usuario_nombre: string | null;
  cedula: string;
  estado: string;
  fecha_envio: string | null;
  fecha_decision: string | null;
  revision_reforzada: boolean;
  motivo_rechazo: string | null;
}

function crearSolicitud(overrides: Partial<SolicitudFixture> = {}): SolicitudFixture {
  return {
    id: "sol-1",
    usuario_id: "user-1",
    usuario_nombre: "Juan Pérez",
    cedula: "1712345678",
    estado: "EN_VERIFICACION",
    fecha_envio: "2026-07-20T10:00:00Z",
    fecha_decision: null,
    revision_reforzada: false,
    motivo_rechazo: null,
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
