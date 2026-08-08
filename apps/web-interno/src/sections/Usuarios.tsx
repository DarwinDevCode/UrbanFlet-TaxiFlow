import {
  ActionBar,
  ApiError,
  apiFetch,
  Badge,
  Button,
  Card,
  DataTable,
  DetailField,
  DetailPanel,
  invalidateSwrPrefix,
  Pagination,
  Select,
  TextArea,
  TextField,
  useSwr,
  type ModoPanel,
} from "@urbanflet/shared-ui";
import { useState } from "react";

const RECURSO_USUARIOS = "/usuarios";

// Mismo catálogo que `usuarios/service.py::ROLES_STAFF` (backend) --
// pasajero/conductor se autorregistran, este módulo no los puede crear.
// Sí se pueden CONSULTAR y GESTIONAR (punto #7 de la ronda de usabilidad,
// 2026-08-07): el backend ya lo permitía (suspender/reactivar/dar-de-baja/
// sesiones no filtran por rol), solo faltaba exponerlo -- ver
// `ROLES_EXTERNOS` más abajo, usado solo para el filtro de búsqueda.
const ROLES_STAFF = [
  "admin_captacion",
  "coordinador_operaciones",
  "coordinador_flota",
  "jefe_mantenimiento",
  "admin_financiero",
  "supervisor_cumplimiento",
  "responsable_plataforma",
  "gerencia",
  "integracion_externa",
  "admin_plataforma",
  "admin_sistema",
];

const ROLES_EXTERNOS = ["conductor", "pasajero"];

function esCuentaExterna(roles: string[]): boolean {
  return roles.some((r) => ROLES_EXTERNOS.includes(r));
}

interface Usuario {
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

interface UsuarioListOut {
  items: Usuario[];
  total: number;
}

interface Acceso {
  ts: string;
  accion: string;
  resultado: string;
}

interface Sesion {
  jti: string;
  ip: string | null;
  dispositivo: string | null;
  ts_inicio: string | null;
}

const tonoPorEstado: Record<string, "neutral" | "exito" | "advertencia" | "peligro"> = {
  ACTIVO: "exito",
  SUSPENDIDO: "advertencia",
  BAJA: "peligro",
};

function RolesCheckboxes({ seleccionados, onChange }: { seleccionados: string[]; onChange: (roles: string[]) => void }) {
  const alternar = (rol: string) => {
    onChange(seleccionados.includes(rol) ? seleccionados.filter((r) => r !== rol) : [...seleccionados, rol]);
  };
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "var(--space-2)" }}>
      {ROLES_STAFF.map((rol) => (
        <label key={rol} style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", fontSize: "var(--font-size-sm)" }}>
          <input type="checkbox" checked={seleccionados.includes(rol)} onChange={() => alternar(rol)} />
          {rol}
        </label>
      ))}
    </div>
  );
}

export function SeccionUsuarios() {
  const [filtroRol, setFiltroRol] = useState("");
  const [filtroEstado, setFiltroEstado] = useState("");
  const [textoInput, setTextoInput] = useState("");
  const [filtroTexto, setFiltroTexto] = useState("");
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(20);

  const [seleccionado, setSeleccionado] = useState<Usuario | null>(null);
  const [modo, setModo] = useState<ModoPanel>("consulta");
  const [errorAccion, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  // Formulario de creación / edición.
  const [nombre, setNombre] = useState("");
  const [telefono, setTelefono] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rolesForm, setRolesForm] = useState<string[]>([]);

  // Motivo de suspensión/baja.
  const [motivo, setMotivo] = useState("");
  const [accionMotivo, setAccionMotivo] = useState<"suspender" | "dar-de-baja" | null>(null);

  const [accesos, setAccesos] = useState<Acceso[]>([]);
  const [sesiones, setSesiones] = useState<Sesion[]>([]);

  const claveConsulta = (() => {
    const params = new URLSearchParams();
    if (filtroRol) params.set("rol", filtroRol);
    if (filtroEstado) params.set("estado", filtroEstado);
    if (filtroTexto) params.set("texto", filtroTexto);
    params.set("limit", String(pageSize));
    params.set("offset", String(page * pageSize));
    return `${RECURSO_USUARIOS}?${params.toString()}`;
  })();
  const { data, error: errorCarga, refetch } = useSwr<UsuarioListOut>(claveConsulta, () =>
    apiFetch<UsuarioListOut>(claveConsulta),
  );
  const usuarios = data?.items ?? [];
  const total = data?.total ?? 0;
  const error =
    errorAccion ??
    (errorCarga ? (errorCarga instanceof ApiError ? errorCarga.message : "No se pudieron cargar los usuarios") : null);

  const buscar = () => {
    setFiltroTexto(textoInput.trim());
    setPage(0);
  };

  const limpiarBusqueda = () => {
    setFiltroRol("");
    setFiltroEstado("");
    setTextoInput("");
    setFiltroTexto("");
    setPage(0);
    setSeleccionado(null);
  };

  const abrirNuevo = () => {
    setSeleccionado(null);
    setModo("nuevo");
    setNombre("");
    setTelefono("");
    setEmail("");
    setPassword("");
    setRolesForm([]);
    setError(null);
  };

  const cargarDetalle = async (u: Usuario) => {
    setSeleccionado(u);
    setModo("consulta");
    setRolesForm(u.roles);
    setMotivo("");
    setAccionMotivo(null);
    setError(null);
    setAccesos([]);
    setSesiones([]);
    try {
      const [listaAccesos, listaSesiones] = await Promise.all([
        apiFetch<Acceso[]>(`/usuarios/${u.id}/accesos`),
        apiFetch<Sesion[]>(`/usuarios/${u.id}/sesiones`),
      ]);
      setAccesos(listaAccesos);
      setSesiones(listaSesiones);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo cargar el historial de la cuenta");
    }
  };

  const crear = async () => {
    setError(null);
    setCargando(true);
    try {
      await apiFetch("/usuarios", {
        method: "POST",
        body: {
          nombre,
          telefono: telefono || undefined,
          email: email || undefined,
          password,
          roles: rolesForm,
        },
      });
      setSeleccionado(null);
      setModo("consulta");
      setNombre("");
      setTelefono("");
      setEmail("");
      setPassword("");
      setRolesForm([]);
      invalidateSwrPrefix(RECURSO_USUARIOS);
      await refetch();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo crear la cuenta");
    } finally {
      setCargando(false);
    }
  };

  const guardarRoles = async () => {
    if (!seleccionado) return;
    setError(null);
    setCargando(true);
    try {
      const actualizado = await apiFetch<Usuario>(`/usuarios/${seleccionado.id}/roles`, {
        method: "POST",
        body: { roles: rolesForm },
      });
      setSeleccionado(actualizado);
      invalidateSwrPrefix(RECURSO_USUARIOS);
      await refetch();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudieron actualizar los roles");
    } finally {
      setCargando(false);
    }
  };

  const confirmarMotivo = async () => {
    if (!seleccionado || !accionMotivo) return;
    setError(null);
    setCargando(true);
    try {
      const actualizado = await apiFetch<Usuario>(`/usuarios/${seleccionado.id}/${accionMotivo}`, {
        method: "POST",
        body: { motivo },
      });
      setSeleccionado(actualizado);
      setAccionMotivo(null);
      setMotivo("");
      invalidateSwrPrefix(RECURSO_USUARIOS);
      await refetch();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo completar la acción");
    } finally {
      setCargando(false);
    }
  };

  const reactivar = async () => {
    if (!seleccionado) return;
    setError(null);
    setCargando(true);
    try {
      const actualizado = await apiFetch<Usuario>(`/usuarios/${seleccionado.id}/reactivar`, { method: "POST" });
      setSeleccionado(actualizado);
      invalidateSwrPrefix(RECURSO_USUARIOS);
      await refetch();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo reactivar la cuenta");
    } finally {
      setCargando(false);
    }
  };

  const cerrarSesion = async (jti: string) => {
    if (!seleccionado) return;
    try {
      await apiFetch(`/usuarios/${seleccionado.id}/sesiones/${jti}`, { method: "DELETE" });
      setSesiones((prev) => prev.filter((s) => s.jti !== jti));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo cerrar la sesión");
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <Card>
        <h2 style={{ marginTop: 0, fontSize: "var(--font-size-lg)" }}>Buscar cuentas</h2>
        <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
          Incluye personal interno, conductores y pasajeros. Conductores y pasajeros se autorregistran desde las
          apps públicas (CU-O01/CU-O02) — aquí se pueden consultar, suspender/reactivar, dar de baja y gestionar
          sus sesiones activas, pero no crear: crear uno a mano saltaría el flujo de verificación documental.
        </p>
        <div style={{ display: "flex", gap: "var(--space-3)", flexWrap: "wrap", alignItems: "flex-end" }}>
          <div style={{ minWidth: 220 }}>
            <Select
              label="Rol"
              value={filtroRol}
              onChange={(e) => {
                setFiltroRol(e.target.value);
                setPage(0);
              }}
              options={[
                { value: "", label: "Todos" },
                ...ROLES_STAFF.map((r) => ({ value: r, label: r })),
                ...ROLES_EXTERNOS.map((r) => ({ value: r, label: r })),
              ]}
            />
          </div>
          <div style={{ minWidth: 180 }}>
            <Select
              label="Estado"
              value={filtroEstado}
              onChange={(e) => {
                setFiltroEstado(e.target.value);
                setPage(0);
              }}
              options={[
                { value: "", label: "Todos" },
                { value: "ACTIVO", label: "Activo" },
                { value: "SUSPENDIDO", label: "Suspendido" },
                { value: "BAJA", label: "Baja" },
              ]}
            />
          </div>
          <div style={{ minWidth: 220 }}>
            <TextField
              label="Nombre, teléfono o correo"
              value={textoInput}
              onChange={(e) => setTextoInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && buscar()}
            />
          </div>
        </div>
      </Card>

      <ActionBar
        nuevo={{ onClick: abrirNuevo }}
        actualizar={{ onClick: () => refetch() }}
        eliminar={{
          onClick: () => {},
          disabled: true,
          title: "No aplica: las cuentas no se eliminan, se suspenden o se dan de baja.",
        }}
        buscar={{ onClick: buscar }}
        salir={{ onClick: limpiarBusqueda }}
      />

      <Card>
        {error && !seleccionado && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}

        <DataTable
          rows={usuarios}
          keyField={(u) => u.id}
          vacio="No hay cuentas con este filtro."
          columns={[
            { header: "Nombre", render: (u) => u.nombre },
            { header: "Contacto", render: (u) => u.telefono ?? u.email ?? "—" },
            { header: "Roles", render: (u) => u.roles.join(", ") || "—" },
            { header: "Estado", render: (u) => <Badge texto={u.estado} tono={tonoPorEstado[u.estado] ?? "neutral"} /> },
            {
              header: "Detalle",
              render: (u) => (
                <Button variant="secondary" onClick={() => cargarDetalle(u)}>
                  Ver
                </Button>
              ),
            },
          ]}
        />
        <Pagination page={page} pageSize={pageSize} total={total} onPageChange={setPage} onPageSizeChange={(n) => { setPageSize(n); setPage(0); }} />
      </Card>

      {modo === "nuevo" && (
        <DetailPanel
          titulo="Nueva cuenta de personal interno"
          modo="nuevo"
          onSalir={() => setModo("consulta")}
          onAceptar={crear}
          aceptarLabel="Crear cuenta"
          aceptarDisabled={!nombre || (!telefono && !email) || !password || rolesForm.length === 0}
          aceptarLoading={cargando}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
            {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "var(--space-3)" }}>
              <TextField label="Nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} />
              <TextField label="Teléfono" value={telefono} onChange={(e) => setTelefono(e.target.value)} />
              <TextField label="Correo" value={email} onChange={(e) => setEmail(e.target.value)} />
              <TextField label="Contraseña inicial" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
            <div>
              <p style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)", marginBottom: "var(--space-2)" }}>
                Roles (la cuenta deberá cambiar la contraseña en su primer inicio de sesión)
              </p>
              <RolesCheckboxes seleccionados={rolesForm} onChange={setRolesForm} />
            </div>
          </div>
        </DetailPanel>
      )}

      {seleccionado && modo !== "nuevo" && (
        <DetailPanel
          titulo={`Cuenta — ${seleccionado.nombre}`}
          modo={modo}
          onSalir={() => setSeleccionado(null)}
          accionesExtra={
            <>
              {seleccionado.estado === "ACTIVO" && (
                <div style={{ minWidth: 140 }}>
                  <Button variant="secondary" onClick={() => setAccionMotivo("suspender")}>
                    Suspender
                  </Button>
                </div>
              )}
              {seleccionado.estado === "SUSPENDIDO" && (
                <div style={{ minWidth: 140 }}>
                  <Button variant="secondary" onClick={reactivar} loading={cargando}>
                    Reactivar
                  </Button>
                </div>
              )}
              {seleccionado.estado !== "BAJA" && (
                <div style={{ minWidth: 140 }}>
                  <Button variant="secondary" onClick={() => setAccionMotivo("dar-de-baja")}>
                    Dar de baja
                  </Button>
                </div>
              )}
            </>
          }
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
            {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "var(--space-3)" }}>
              <DetailField label="Nombre" value={seleccionado.nombre} />
              <DetailField label="Teléfono" value={seleccionado.telefono ?? "—"} />
              <DetailField label="Correo" value={seleccionado.email ?? "—"} />
              <DetailField label="Estado" value={<Badge texto={seleccionado.estado} tono={tonoPorEstado[seleccionado.estado] ?? "neutral"} />} />
              <DetailField label="Alta" value={new Date(seleccionado.fecha_registro).toLocaleDateString()} />
              <DetailField label="Motivo suspensión/baja" value={seleccionado.motivo_suspension ?? seleccionado.motivo_baja ?? "—"} />
            </div>

            {accionMotivo && (
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", borderTop: "1px solid var(--color-border)", paddingTop: "var(--space-3)" }}>
                <TextArea label="Motivo (obligatorio)" value={motivo} onChange={(e) => setMotivo(e.target.value)} />
                <div style={{ display: "flex", gap: "var(--space-2)" }}>
                  <div style={{ minWidth: 140 }}>
                    <Button onClick={confirmarMotivo} disabled={motivo.trim().length < 3} loading={cargando}>
                      Confirmar {accionMotivo === "suspender" ? "suspensión" : "baja"}
                    </Button>
                  </div>
                  <div style={{ minWidth: 100 }}>
                    <Button variant="secondary" onClick={() => setAccionMotivo(null)}>
                      Cancelar
                    </Button>
                  </div>
                </div>
              </div>
            )}

            <div style={{ borderTop: "1px solid var(--color-border)", paddingTop: "var(--space-3)" }}>
              <p style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)", marginBottom: "var(--space-2)" }}>
                Roles asignados
              </p>
              {esCuentaExterna(seleccionado.roles) ? (
                <p
                  style={{ fontSize: "var(--font-size-sm)" }}
                  title="No editable: pasajero/conductor son roles de autorregistro (CU-O01/CU-O02) — el backend no permite reasignarlos a un rol de personal interno ni viceversa por este canal."
                >
                  {seleccionado.roles.join(", ")} <span style={{ color: "var(--color-text-muted)" }}>(no editable aquí)</span>
                </p>
              ) : (
                <>
                  <RolesCheckboxes seleccionados={rolesForm} onChange={setRolesForm} />
                  <div style={{ marginTop: "var(--space-3)", minWidth: 160 }}>
                    <Button variant="secondary" onClick={guardarRoles} disabled={rolesForm.length === 0} loading={cargando}>
                      Guardar roles
                    </Button>
                  </div>
                </>
              )}
            </div>

            <div style={{ borderTop: "1px solid var(--color-border)", paddingTop: "var(--space-3)" }}>
              <p style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)", marginBottom: "var(--space-2)" }}>
                Sesiones activas
              </p>
              {sesiones.length === 0 ? (
                <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>Ninguna sesión activa.</p>
              ) : (
                <ul style={{ margin: 0, paddingLeft: "var(--space-4)" }}>
                  {sesiones.map((s) => (
                    <li key={s.jti} style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", marginBottom: "var(--space-1)" }}>
                      <span style={{ fontSize: "var(--font-size-sm)" }}>
                        {s.dispositivo ?? "Dispositivo desconocido"} — {s.ip ?? "IP desconocida"}
                      </span>
                      <Button variant="secondary" onClick={() => cerrarSesion(s.jti)}>
                        Cerrar sesión
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div style={{ borderTop: "1px solid var(--color-border)", paddingTop: "var(--space-3)" }}>
              <p style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)", marginBottom: "var(--space-2)" }}>
                Historial de accesos (inicios de sesión e intentos fallidos)
              </p>
              {accesos.length === 0 ? (
                <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>Sin eventos registrados.</p>
              ) : (
                <ul style={{ margin: 0, paddingLeft: "var(--space-4)" }}>
                  {accesos.map((a, i) => (
                    <li key={i} style={{ fontSize: "var(--font-size-sm)" }}>
                      {new Date(a.ts).toLocaleString()} — {a.accion} ({a.resultado})
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </DetailPanel>
      )}
    </div>
  );
}
