import {
  AjustesPropios,
  ApiError,
  AppShell,
  Button,
  Card,
  CentroAyuda,
  logoUrbanFleetFull,
  NotificacionesBell,
  PerfilPropio,
  TextField,
  useAuth,
  type PreguntaFrecuente,
} from "@urbanflet/shared-ui";
import { useState } from "react";
import { SeccionAuditoriaAdmin } from "./sections/AuditoriaAdmin";
import { SeccionCatalogos } from "./sections/Catalogos";
import { SeccionConfiguracionAlertas } from "./sections/ConfiguracionAlertas";
import { SeccionCumplimiento } from "./sections/Cumplimiento";
import { SeccionFeatureFlags } from "./sections/FeatureFlags";
import { SeccionFinanzas } from "./sections/Finanzas";
import { SeccionFlota } from "./sections/Flota";
import { SeccionGobernanzaDatos } from "./sections/GobernanzaDatos";
import { SeccionHistorialGlobal } from "./sections/HistorialGlobal";
import { SeccionIndicadores } from "./sections/Indicadores";
import { SeccionIntegraciones } from "./sections/Integraciones";
import { SeccionMantenimiento } from "./sections/Mantenimiento";
import { SeccionMonitoreo } from "./sections/Monitoreo";
import { SeccionParametrosGlobales } from "./sections/ParametrosGlobales";
import { SeccionPoliticasAuth } from "./sections/PoliticasAuth";
import { SeccionPoliticasSeguridad } from "./sections/PoliticasSeguridad";
import { SeccionRespaldosYContinuidad } from "./sections/Respaldos";
import { SeccionSolicitudes } from "./sections/Solicitudes";
import { SeccionUsuarios } from "./sections/Usuarios";
import { SeccionVersionSistema } from "./sections/VersionSistema";
import { PanelAuditoria } from "./sections/tactico/PanelAuditoria";
import { PanelCaptacion } from "./sections/tactico/PanelCaptacion";
import { PanelConciliacion } from "./sections/tactico/PanelConciliacion";
import { PanelDespacho } from "./sections/tactico/PanelDespacho";
import { PanelDocumentacion } from "./sections/tactico/PanelDocumentacion";
import { PanelLiquidacion } from "./sections/tactico/PanelLiquidacion";
import { PanelPlataforma } from "./sections/tactico/PanelPlataforma";
import { PanelFlota } from "./sections/tactico/PanelFlota";
import { PanelMantenimiento } from "./sections/tactico/PanelMantenimiento";

function LoginCard() {
  const { login } = useAuth();
  const [identificador, setIdentificador] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  const entrar = async () => {
    setError(null);
    setCargando(true);
    try {
      await login(identificador, password);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Credenciales inválidas");
    } finally {
      setCargando(false);
    }
  };

  return (
    <div style={{ minHeight: "100dvh", display: "flex", alignItems: "center", justifyContent: "center", padding: "var(--space-4)" }}>
      <div style={{ width: "min(420px, 100%)" }}>
        <div style={{ display: "flex", justifyContent: "center", marginBottom: "var(--space-4)" }}>
          <img src={logoUrbanFleetFull} alt="UrbanFleet" style={{ width: 160, maxWidth: "100%", height: "auto" }} />
        </div>
        <Card>
          <h1 style={{ fontSize: "var(--font-size-lg)", margin: 0, marginBottom: "var(--space-2)" }}>
            Portal interno
          </h1>
          <p style={{ color: "var(--color-text-muted)", marginTop: 0, marginBottom: "var(--space-4)" }}>
            Jefes de área y gerencia — acceso con teléfono o correo, y contraseña.
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            <TextField
              label="Teléfono o correo"
              value={identificador}
              onChange={(e) => setIdentificador(e.target.value)}
            />
            <TextField
              label="Contraseña"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            {error && <span style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</span>}
            <Button onClick={entrar} loading={cargando} disabled={!identificador || !password}>
              Entrar
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
}

interface Seccion {
  id: string;
  etiqueta: string;
  roles: string[];
  grupo?: string;
  render: () => JSX.Element;
}

// Sección 3.1 de la spec ux_complementaria.md: visible para los 13 roles de
// `web-interno`, no filtrada por rol como el resto -- `ROL_CUALQUIERA` es un
// sentinel que `Panel()` reconoce más abajo, en vez de listar los 13 roles a
// mano (se rompería en cuanto se agregue un rol 14 nuevo).
const ROL_CUALQUIERA = "*";

const PREGUNTAS_FRECUENTES_INTERNO: PreguntaFrecuente[] = [
  {
    pregunta: "¿Por qué no veo ninguna sección?",
    respuesta: "Tu cuenta no tiene ningún rol con una pantalla asignada todavía — pide al Administrador del Sistema que revise tus roles.",
  },
  {
    pregunta: "¿Cómo actualizo mi propio teléfono o correo?",
    respuesta: "Entra a \"Mi cuenta\" y edita tus datos con tu contraseña actual. No necesitas pedírselo a un administrador.",
  },
  {
    pregunta: "¿Puedo cambiar mi propio rol?",
    respuesta: "No — los roles solo los asigna el Administrador del Sistema desde el módulo de Usuarios.",
  },
];

const SECCIONES: Seccion[] = [
  { id: "solicitudes", etiqueta: "Solicitudes", roles: ["admin_captacion"], render: () => <SeccionSolicitudes /> },
  { id: "mantenimiento", etiqueta: "Mantenimiento", roles: ["jefe_mantenimiento"], render: () => <SeccionMantenimiento /> },
  { id: "cumplimiento", etiqueta: "Cumplimiento", roles: ["supervisor_cumplimiento"], render: () => <SeccionCumplimiento /> },
  { id: "flota", etiqueta: "Flota", roles: ["coordinador_flota", "admin_plataforma"], render: () => <SeccionFlota /> },
  { id: "finanzas", etiqueta: "Finanzas", roles: ["admin_financiero"], render: () => <SeccionFinanzas /> },
  {
    id: "indicadores",
    etiqueta: "Indicadores",
    roles: ["gerencia", "responsable_plataforma", "admin_plataforma"],
    render: () => <SeccionIndicadores />,
  },
  {
    id: "tactico-flota",
    etiqueta: "Flota (táctico)",
    roles: ["coordinador_flota", "admin_plataforma"],
    grupo: "Panel Táctico",
    render: () => <PanelFlota />,
  },
  {
    id: "tactico-mantenimiento",
    etiqueta: "Mantenimiento (táctico)",
    roles: ["jefe_mantenimiento"],
    grupo: "Panel Táctico",
    render: () => <PanelMantenimiento />,
  },
  {
    id: "tactico-documentacion",
    etiqueta: "Vigencia Documental (táctico)",
    roles: ["supervisor_cumplimiento"],
    grupo: "Panel Táctico",
    render: () => <PanelDocumentacion />,
  },
  {
    id: "tactico-captacion",
    etiqueta: "Captación (táctico)",
    roles: ["admin_captacion"],
    grupo: "Panel Táctico",
    render: () => <PanelCaptacion />,
  },
  {
    id: "tactico-despacho",
    etiqueta: "Despacho (táctico)",
    roles: ["coordinador_operaciones"],
    grupo: "Panel Táctico",
    render: () => <PanelDespacho />,
  },
  {
    id: "tactico-conciliacion",
    etiqueta: "Conciliación (táctico)",
    roles: ["admin_financiero"],
    grupo: "Panel Táctico",
    render: () => <PanelConciliacion />,
  },
  {
    id: "tactico-liquidacion",
    etiqueta: "Liquidación (táctico)",
    roles: ["admin_financiero"],
    grupo: "Panel Táctico",
    render: () => <PanelLiquidacion />,
  },
  {
    id: "tactico-auditoria",
    etiqueta: "Auditoría (táctico)",
    roles: ["supervisor_cumplimiento", "admin_plataforma", "gerencia"],
    grupo: "Panel Táctico",
    render: () => <PanelAuditoria />,
  },
  {
    id: "tactico-plataforma",
    etiqueta: "Plataforma (táctico)",
    roles: ["gerencia", "responsable_plataforma", "admin_plataforma"],
    grupo: "Panel Táctico",
    render: () => <PanelPlataforma />,
  },
  {
    id: "admin-usuarios",
    etiqueta: "Usuarios",
    roles: ["admin_sistema"],
    grupo: "Administración",
    render: () => <SeccionUsuarios />,
  },
  {
    id: "admin-politicas-auth",
    etiqueta: "Políticas de autenticación",
    roles: ["admin_sistema"],
    grupo: "Administración",
    render: () => <SeccionPoliticasAuth />,
  },
  {
    id: "admin-parametros-globales",
    etiqueta: "Parámetros globales",
    roles: ["admin_sistema"],
    grupo: "Administración",
    render: () => <SeccionParametrosGlobales />,
  },
  {
    id: "admin-feature-flags",
    etiqueta: "Funcionalidades",
    roles: ["admin_sistema"],
    grupo: "Administración",
    render: () => <SeccionFeatureFlags />,
  },
  {
    id: "admin-auditoria",
    etiqueta: "Auditoría",
    roles: ["admin_sistema"],
    grupo: "Administración",
    render: () => <SeccionAuditoriaAdmin />,
  },
  {
    id: "admin-catalogos",
    etiqueta: "Catálogos",
    roles: ["admin_sistema"],
    grupo: "Administración",
    render: () => <SeccionCatalogos />,
  },
  {
    id: "admin-version",
    etiqueta: "Versión",
    roles: ["admin_sistema"],
    grupo: "Administración",
    render: () => <SeccionVersionSistema />,
  },
  {
    id: "admin-politicas-seguridad",
    etiqueta: "Políticas de seguridad",
    roles: ["admin_sistema"],
    grupo: "Administración",
    render: () => <SeccionPoliticasSeguridad />,
  },
  {
    id: "admin-notificaciones",
    etiqueta: "Notificaciones",
    roles: ["admin_sistema"],
    grupo: "Administración",
    render: () => <SeccionConfiguracionAlertas />,
  },
  {
    id: "admin-integraciones",
    etiqueta: "Integraciones",
    roles: ["admin_sistema"],
    grupo: "Administración",
    render: () => <SeccionIntegraciones />,
  },
  {
    id: "admin-monitoreo",
    etiqueta: "Monitoreo",
    roles: ["admin_sistema"],
    grupo: "Administración",
    render: () => <SeccionMonitoreo />,
  },
  {
    id: "admin-gobernanza-datos",
    etiqueta: "Gobernanza de datos",
    roles: ["admin_sistema"],
    grupo: "Administración",
    render: () => <SeccionGobernanzaDatos />,
  },
  {
    id: "admin-respaldos",
    etiqueta: "Respaldos",
    roles: ["admin_sistema", "gerencia"],
    grupo: "Administración",
    render: () => <SeccionRespaldosYContinuidad />,
  },
  {
    // Sección 3.3 de ux_complementaria.md: acceso restringido por rol
    // (principio de mínimo privilegio ya aplicado en Administración) --
    // distinto grupo del sidebar, no es ni un CRUD operativo ni un panel
    // táctico de agregados, es una consulta puntual de cualquier viaje.
    // Colocado DESPUÉS de todos los grupos con roles únicos (Solicitudes,
    // Mantenimiento, Panel Táctico, Administración) -- mismo motivo que
    // "Mi cuenta" más abajo: no debe convertirse en la sección por defecto
    // de ningún rol ya existente (`seccionesVisibles[0]`), ya que
    // `admin_sistema` (entre otros) también calificaría para esta sección.
    id: "historial-global",
    etiqueta: "Historial de viajes",
    roles: ["coordinador_operaciones", "supervisor_cumplimiento", "gerencia", "admin_sistema"],
    grupo: "Historial",
    render: () => <SeccionHistorialGlobal />,
  },
  // Sección 3.1 de la spec ux_complementaria.md: visible para los 13 roles
  // de `web-interno`, no filtrada por rol como el resto de la lista --
  // `ROL_CUALQUIERA` es un sentinel que `Panel()` reconoce más abajo, en vez
  // de listar los 13 roles a mano (se rompería en cuanto se agregue un rol
  // 14 nuevo). Al final de la lista a propósito: no debe convertirse en la
  // sección por defecto de ningún rol ya existente (`seccionesVisibles[0]`).
  {
    id: "mi-cuenta",
    etiqueta: "Mi cuenta",
    roles: [ROL_CUALQUIERA],
    render: () => <PerfilPropio />,
  },
  {
    id: "ajustes",
    etiqueta: "Ajustes",
    roles: [ROL_CUALQUIERA],
    render: () => <AjustesPropios version="0.1.0" mostrarDensidad />,
  },
  {
    id: "ayuda",
    etiqueta: "Ayuda",
    roles: [ROL_CUALQUIERA],
    render: () => (
      <CentroAyuda
        preguntas={PREGUNTAS_FRECUENTES_INTERNO}
        correoContacto="soporte@urbanfleet.example"
        telefonoContacto="+593900000000"
      />
    ),
  },
];

function Panel() {
  const { actor } = useAuth();
  const rolesActor = actor?.roles ?? [];
  // Misma lógica de filtrado por rol que antes tenía la nav horizontal — solo
  // cambia dónde se renderiza (sidebar del AppShell en vez de una fila de
  // botones bajo un header ad-hoc).
  const seccionesVisibles = SECCIONES.filter(
    (s) => s.roles.includes(ROL_CUALQUIERA) || s.roles.some((r) => rolesActor.includes(r)),
  );
  const [seccionActiva, setSeccionActiva] = useState(seccionesVisibles[0]?.id);

  const seccion = seccionesVisibles.find((s) => s.id === seccionActiva);
  const navItems = seccionesVisibles.map((s) => ({ id: s.id, label: s.etiqueta, group: s.grupo }));

  return (
    <AppShell
      navItems={navItems}
      activeId={seccionActiva}
      onNavigate={setSeccionActiva}
      title={seccion?.etiqueta ?? "Portal interno"}
      headerActions={<NotificacionesBell />}
    >
      {seccionesVisibles.length === 0 ? (
        <Card>
          <p style={{ color: "var(--color-text-muted)" }}>
            Tu rol no tiene ninguna sección asignada en este panel todavía.
          </p>
        </Card>
      ) : (
        seccion?.render()
      )}
    </AppShell>
  );
}

// Módulo 1.1/1.3 de admin_sistema (specs/specs-administrativas/
// admin_sistema.md): una cuenta creada por un administrador, o cuya
// contraseña venció según la política vigente, no puede navegar el resto
// del portal hasta cambiarla.
function CambiarPasswordCard() {
  const { cambiarPassword, logout } = useAuth();
  const [actual, setActual] = useState("");
  const [nueva, setNueva] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  const confirmar = async () => {
    setError(null);
    setCargando(true);
    try {
      await cambiarPassword(actual, nueva);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo cambiar la contraseña");
    } finally {
      setCargando(false);
    }
  };

  return (
    <div style={{ minHeight: "100dvh", display: "flex", alignItems: "center", justifyContent: "center", padding: "var(--space-4)" }}>
      <div style={{ width: "min(420px, 100%)" }}>
        <Card>
          <h1 style={{ fontSize: "var(--font-size-lg)", margin: 0, marginBottom: "var(--space-2)" }}>
            Cambio de contraseña obligatorio
          </h1>
          <p style={{ color: "var(--color-text-muted)", marginTop: 0, marginBottom: "var(--space-4)" }}>
            Un administrador forzó el cambio de contraseña de esta cuenta, o la política de vencimiento periódico ya
            expiró. Debes definir una nueva contraseña antes de continuar.
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            <TextField label="Contraseña actual" type="password" value={actual} onChange={(e) => setActual(e.target.value)} />
            <TextField label="Contraseña nueva" type="password" value={nueva} onChange={(e) => setNueva(e.target.value)} />
            {error && <span style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</span>}
            <Button onClick={confirmar} loading={cargando} disabled={!actual || !nueva}>
              Cambiar contraseña
            </Button>
            <Button variant="secondary" onClick={logout}>
              Cancelar y salir
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
}

export default function App() {
  const { actor, debeCambiarPassword } = useAuth();
  if (!actor) return <LoginCard />;
  if (debeCambiarPassword) return <CambiarPasswordCard />;
  return <Panel />;
}
