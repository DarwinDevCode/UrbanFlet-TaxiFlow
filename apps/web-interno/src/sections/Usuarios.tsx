import {
  ActionBar,
  Alert,
  ApiError,
  apiFetch,
  Avatar,
  Badge,
  Button,
  Card,
  DataTable,
  DetailField,
  DetailPanel,
  EvidenciaImagen,
  invalidateSwrPrefix,
  nombreRol,
  nombreTipoDocumento,
  Pagination,
  PasswordField,
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
  foto_url: string | null;
}

/** Fila de `GET /cumplimiento/documentos/conductor/{id}` (mismo shape que
 * `MiDocumentoOut`, el autoservicio del conductor). */
interface DocumentoConductor {
  id: string;
  tipo: string;
  fecha_vencimiento: string | null;
  estado_verificacion: string;
  dias_restantes: number | null;
  tiene_renovacion_pendiente: boolean;
  archivo_id: string | null;
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
          {nombreRol(rol)}
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
  const [passwordConfirmar, setPasswordConfirmar] = useState("");
  // Ronda de correcciones (agosto 2026): por defecto se genera sola -- el
  // campo manual solo se habilita si `admin_sistema` decide desmarcarlo.
  const [passwordAuto, setPasswordAuto] = useState(true);
  // Contraseña devuelta por el backend, visible UNA sola vez -- ni la crea
  // ni la restablece guarda el valor en texto plano, así que si se pierde
  // esta pantalla no hay forma de recuperarla (mismo criterio ya usado por
  // el secreto de una credencial de integración, ver Integraciones.tsx).
  const [passwordGenerada, setPasswordGenerada] = useState<string | null>(null);
  const [passwordRestablecida, setPasswordRestablecida] = useState<string | null>(null);
  const [rolesForm, setRolesForm] = useState<string[]>([]);

  // Motivo de suspensión/baja.
  const [motivo, setMotivo] = useState("");
  const [accionMotivo, setAccionMotivo] = useState<"suspender" | "dar-de-baja" | null>(null);

  const [accesos, setAccesos] = useState<Acceso[]>([]);
  const [sesiones, setSesiones] = useState<Sesion[]>([]);
  // Estado documental del socio, solo para cuentas con rol `conductor`.
  // Cierra el último gap de aprovechamiento downstream de la gestión
  // documental: hasta ahora, el personal interno no tenía NINGUNA pantalla
  // donde consultar de un vistazo si un conductor tiene la documentación al
  // día -- solo bandejas agregadas por documento (Vigencia Documental), nunca
  // por persona.
  const [documentos, setDocumentos] = useState<DocumentoConductor[]>([]);

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
    setPasswordConfirmar("");
    setPasswordAuto(true);
    setPasswordGenerada(null);
    setRolesForm([]);
    setError(null);
  };

  const cargarDetalle = async (u: Usuario) => {
    setSeleccionado(u);
    setModo("consulta");
    setRolesForm(u.roles);
    // Prefill del formulario de contacto (Fase C item 1) -- se reusan los
    // mismos 3 campos de estado que ya usa "Nuevo", no se duplican.
    setNombre(u.nombre);
    setTelefono(u.telefono ?? "");
    setEmail(u.email ?? "");
    setMotivo("");
    setAccionMotivo(null);
    setError(null);
    setAccesos([]);
    setSesiones([]);
    setDocumentos([]);
    setPasswordRestablecida(null);
    // Solo se pide para conductores: para cualquier otro rol la respuesta
    // sería siempre vacía (no tiene documentos ni vehículos) y sería una
    // petición de más en cada apertura de detalle.
    if (u.roles.includes("conductor")) {
      apiFetch<DocumentoConductor[]>(`/cumplimiento/documentos/conductor/${u.id}`)
        .then(setDocumentos)
        .catch(() => setDocumentos([]));
    }
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
      const creado = await apiFetch<Usuario & { password_generada: string | null }>("/usuarios", {
        method: "POST",
        body: {
          nombre,
          telefono: telefono || undefined,
          email: email || undefined,
          password: passwordAuto ? undefined : password,
          roles: rolesForm,
        },
      });
      invalidateSwrPrefix(RECURSO_USUARIOS);
      await refetch();
      if (creado.password_generada) {
        // No se cierra el panel todavía -- hay que mostrar la contraseña
        // generada una sola vez antes de que se pierda para siempre.
        setPasswordGenerada(creado.password_generada);
      } else {
        setSeleccionado(null);
        setModo("consulta");
        setNombre("");
        setTelefono("");
        setEmail("");
        setPassword("");
        setRolesForm([]);
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo crear la cuenta");
    } finally {
      setCargando(false);
    }
  };

  const restablecerPassword = async () => {
    if (!seleccionado) return;
    setError(null);
    setCargando(true);
    try {
      const resp = await apiFetch<{ password_generada: string }>(
        `/usuarios/${seleccionado.id}/restablecer-password`,
        { method: "POST" },
      );
      setPasswordRestablecida(resp.password_generada);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo restablecer la contraseña");
    } finally {
      setCargando(false);
    }
  };

  // PROPUESTA_CRUD_Y_BAJA_LOGICA.md, Fase C item 1: el backend ya exponía
  // `PATCH /usuarios/{id}` (nombre/teléfono/correo) desde el Módulo 1, pero
  // ninguna pantalla lo llamaba -- corregir el dato mal tecleado de otra
  // persona solo era posible si esa persona lo hacía desde "Mi cuenta" con
  // su propia contraseña. Se envían los 3 campos siempre: el backend ya
  // valida unicidad de teléfono/correo y audita el cambio (USUARIO_EDICION).
  const guardarContacto = async () => {
    if (!seleccionado) return;
    setError(null);
    setCargando(true);
    try {
      const actualizado = await apiFetch<Usuario>(`/usuarios/${seleccionado.id}`, {
        method: "PATCH",
        body: { nombre, telefono: telefono || undefined, email: email || undefined },
      });
      setSeleccionado(actualizado);
      invalidateSwrPrefix(RECURSO_USUARIOS);
      await refetch();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudieron guardar los datos de contacto");
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
          apps públicas — aquí se pueden consultar, suspender/reactivar, dar de baja y gestionar
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
                ...ROLES_STAFF.map((r) => ({ value: r, label: nombreRol(r) })),
                ...ROLES_EXTERNOS.map((r) => ({ value: r, label: nombreRol(r) })),
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

      {/* "Eliminar" quitado (segunda pasada, punto 1): las cuentas no se
          eliminan, se suspenden o se dan de baja -- ningún rol tiene un uso
          real para eliminar acá. */}
      <ActionBar
        nuevo={{ onClick: abrirNuevo }}
        actualizar={{ onClick: () => refetch() }}
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
            {
              header: "Nombre",
              render: (u) => (
                <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                  <Avatar fotoUrl={u.foto_url} nombre={u.nombre} tamano={28} />
                  {u.nombre}
                </div>
              ),
            },
            { header: "Contacto", render: (u) => u.telefono ?? u.email ?? "—" },
            { header: "Roles", render: (u) => u.roles.map(nombreRol).join(", ") || "—" },
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
          ocultarContador
        />
        <Pagination page={page} pageSize={pageSize} total={total} onPageChange={setPage} onPageSizeChange={(n) => { setPageSize(n); setPage(0); }} />
      </Card>

      {modo === "nuevo" && (
        <DetailPanel
          titulo="Nueva cuenta de personal interno"
          modo="nuevo"
          onSalir={() => { setModo("consulta"); setPasswordGenerada(null); }}
          onAceptar={passwordGenerada ? undefined : crear}
          aceptarLabel="Crear cuenta"
          aceptarDisabled={
            !nombre ||
            (!telefono && !email) ||
            (!passwordAuto && (!password || password !== passwordConfirmar)) ||
            rolesForm.length === 0
          }
          aceptarLoading={cargando}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
            {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
            {passwordGenerada ? (
              <>
                <p style={{ color: "var(--color-warning)", fontWeight: 600 }}>
                  Esta contraseña se muestra una sola vez. Cópiala y comunícasela a la persona ahora — no queda
                  almacenada en texto plano y no se puede volver a mostrar. Deberá cambiarla en su primer inicio de
                  sesión.
                </p>
                <PasswordField label="Contraseña generada" value={passwordGenerada} readOnly />
              </>
            ) : (
              <>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "var(--space-3)" }}>
                  <TextField label="Nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} />
                  <TextField label="Teléfono" value={telefono} onChange={(e) => setTelefono(e.target.value)} />
                  <TextField label="Correo" value={email} onChange={(e) => setEmail(e.target.value)} />
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
                  <label style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", fontSize: "var(--font-size-sm)" }}>
                    <input
                      type="checkbox"
                      checked={passwordAuto}
                      onChange={(e) => { setPasswordAuto(e.target.checked); setPassword(""); setPasswordConfirmar(""); }}
                    />
                    Generar contraseña automáticamente (recomendado)
                  </label>
                  {!passwordAuto && (
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "var(--space-3)" }}>
                      <PasswordField label="Contraseña inicial" value={password} onChange={(e) => setPassword(e.target.value)} />
                      <PasswordField
                        label="Confirmar contraseña"
                        value={passwordConfirmar}
                        onChange={(e) => setPasswordConfirmar(e.target.value)}
                        confirmarContra={password}
                      />
                    </div>
                  )}
                </div>
                <div>
                  <p style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)", marginBottom: "var(--space-2)" }}>
                    Roles (la cuenta deberá cambiar la contraseña en su primer inicio de sesión)
                  </p>
                  <RolesCheckboxes seleccionados={rolesForm} onChange={setRolesForm} />
                </div>
              </>
            )}
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
                <div style={{ minWidth: 160 }}>
                  <Button variant="secondary" onClick={restablecerPassword} loading={cargando}>
                    Restablecer contraseña
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
              <DetailField
                label="Nombre"
                value={
                  <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                    <Avatar fotoUrl={seleccionado.foto_url} nombre={seleccionado.nombre} tamano={40} />
                    {seleccionado.nombre}
                  </div>
                }
              />
              <DetailField label="Teléfono" value={seleccionado.telefono ?? "—"} />
              <DetailField label="Correo" value={seleccionado.email ?? "—"} />
              <DetailField label="Estado" value={<Badge texto={seleccionado.estado} tono={tonoPorEstado[seleccionado.estado] ?? "neutral"} />} />
              <DetailField label="Alta" value={new Date(seleccionado.fecha_registro).toLocaleDateString()} />
              <DetailField label="Motivo suspensión/baja" value={seleccionado.motivo_suspension ?? seleccionado.motivo_baja ?? "—"} />
            </div>

            {/* Contraseña recién restablecida -- se muestra UNA sola vez,
                igual que al crear la cuenta (ver el bloque `passwordGenerada`
                del panel "nuevo"). No se guarda en ningún estado persistente
                ni se puede recuperar si se cierra este panel. */}
            {passwordRestablecida && (
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)", borderTop: "1px solid var(--color-border)", paddingTop: "var(--space-3)" }}>
                <p style={{ color: "var(--color-warning)", fontWeight: 600, margin: 0 }}>
                  Esta contraseña se muestra una sola vez. Cópiala y comunícasela a la persona ahora — no queda
                  almacenada en texto plano y no se puede volver a mostrar. Deberá cambiarla en su próximo inicio de
                  sesión.
                </p>
                <div style={{ maxWidth: 320 }}>
                  <PasswordField label="Contraseña nueva" value={passwordRestablecida} readOnly />
                </div>
              </div>
            )}

            {/* Corregir datos de contacto (PROPUESTA_CRUD_Y_BAJA_LOGICA.md,
                Fase C item 1). Solo sobre una cuenta que no está dada de
                baja: editar los datos de una cuenta cerrada no tiene un caso
                de uso real y confundiría con una reactivación. */}
            {seleccionado.estado !== "BAJA" && !accionMotivo && (
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", borderTop: "1px solid var(--color-border)", paddingTop: "var(--space-3)" }}>
                <p style={{ margin: 0, fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>
                  Corregir datos de contacto. Queda registrado en la bitácora como edición de cuenta.
                </p>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "var(--space-3)" }}>
                  <TextField label="Nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} />
                  <TextField label="Teléfono" value={telefono} onChange={(e) => setTelefono(e.target.value)} />
                  <TextField label="Correo" value={email} onChange={(e) => setEmail(e.target.value)} />
                </div>
                <div style={{ minWidth: 180, maxWidth: 220 }}>
                  <Button onClick={guardarContacto} disabled={!nombre.trim()} loading={cargando}>
                    Guardar contacto
                  </Button>
                </div>
              </div>
            )}

            {accionMotivo && (
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", borderTop: "1px solid var(--color-border)", paddingTop: "var(--space-3)" }}>
                {/* Casos borde de la baja lógica, declarados antes de
                    confirmar en vez de dejarlos en un comportamiento
                    silencioso (ver usuarios/service.py::dar_de_baja_usuario).
                    El viaje activo lo bloquea el backend con un 409 y un
                    mensaje propio; el vehículo habilitado sí se permite, y
                    por eso se avisa acá. */}
                {accionMotivo === "dar-de-baja" && (
                  <p style={{ margin: 0, fontSize: "var(--font-size-sm)", color: "var(--color-accent-deep)" }}>
                    La cuenta deja de poder iniciar sesión de inmediato, pero su historial (viajes, órdenes,
                    bitácora) se conserva intacto. Si la persona tiene un vehículo habilitado a su nombre,
                    ese vehículo <strong>sigue habilitado en la flota</strong> y debe gestionarse por
                    separado desde Mantenimiento. No se puede dar de baja una cuenta con un viaje en curso.
                  </p>
                )}
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
                  title="No editable: pasajero/conductor son roles de autorregistro — el sistema no permite reasignarlos a un rol de personal interno ni viceversa por este canal."
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

            {seleccionado.roles.includes("conductor") && (
              <div style={{ borderTop: "1px solid var(--color-border)", paddingTop: "var(--space-3)" }}>
                <p style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)", marginBottom: "var(--space-2)" }}>
                  Estado documental del socio
                </p>
                {/* Advertencia, nunca bloqueo: esta pantalla no impide
                    ninguna operación por documentación vencida. Activar un
                    bloqueo automático es una decisión operativa de la
                    cooperativa (afecta la capacidad de un socio de trabajar)
                    y queda pendiente, deliberadamente sin activar. */}
                {documentos.some((d) => d.dias_restantes !== null && d.dias_restantes < 0) && (
                  <Alert tono="peligro">
                    Este socio tiene documentación vencida. El sistema no bloquea sus operaciones por este
                    motivo — la decisión de suspenderlo es del personal de la cooperativa.
                  </Alert>
                )}
                {documentos.length === 0 ? (
                  <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
                    Sin documentos registrados para este socio.
                  </p>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
                    {documentos.map((d) => {
                      const vencido = d.dias_restantes !== null && d.dias_restantes < 0;
                      const porVencer = d.dias_restantes !== null && d.dias_restantes >= 0 && d.dias_restantes <= 30;
                      return (
                        <div key={d.id} style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
                          {d.archivo_id ? (
                            <EvidenciaImagen archivoId={d.archivo_id} tamano={48} alt={`Documento ${nombreTipoDocumento(d.tipo)}`} />
                          ) : (
                            <div
                              style={{
                                width: 48,
                                height: 48,
                                flexShrink: 0,
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                                border: "1px dashed var(--color-border)",
                                borderRadius: "var(--radius-sm)",
                                fontSize: "var(--font-size-xs)",
                                color: "var(--color-text-muted)",
                              }}
                            >
                              —
                            </div>
                          )}
                          <div style={{ fontSize: "var(--font-size-sm)" }}>
                            <div>
                              {nombreTipoDocumento(d.tipo)} — vence {d.fecha_vencimiento ? new Date(d.fecha_vencimiento).toLocaleDateString() : "sin fecha"}
                            </div>
                            <div style={{ marginTop: "var(--space-1)" }}>
                              <Badge
                                texto={
                                  d.dias_restantes === null
                                    ? "Sin fecha"
                                    : vencido
                                      ? `Vencido hace ${Math.abs(d.dias_restantes)} d`
                                      : porVencer
                                        ? `Vence en ${d.dias_restantes} d`
                                        : "Vigente"
                                }
                                tono={vencido ? "peligro" : porVencer ? "advertencia" : d.dias_restantes === null ? "neutral" : "exito"}
                              />
                              {d.tiene_renovacion_pendiente && (
                                <span style={{ color: "var(--color-text-muted)" }}> · renovación pendiente de revisión</span>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

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
