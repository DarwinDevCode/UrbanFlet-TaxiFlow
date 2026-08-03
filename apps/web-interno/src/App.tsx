import { ApiError, AppShell, Button, Card, TextField, useAuth } from "@urbanflet/shared-ui";
import { useState } from "react";
import { SeccionCumplimiento } from "./sections/Cumplimiento";
import { SeccionFinanzas } from "./sections/Finanzas";
import { SeccionFlota } from "./sections/Flota";
import { SeccionIndicadores } from "./sections/Indicadores";
import { SeccionMantenimiento } from "./sections/Mantenimiento";
import { SeccionSolicitudes } from "./sections/Solicitudes";
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
];

function Panel() {
  const { actor } = useAuth();
  const rolesActor = actor?.roles ?? [];
  // Misma lógica de filtrado por rol que antes tenía la nav horizontal — solo
  // cambia dónde se renderiza (sidebar del AppShell en vez de una fila de
  // botones bajo un header ad-hoc).
  const seccionesVisibles = SECCIONES.filter((s) => s.roles.some((r) => rolesActor.includes(r)));
  const [seccionActiva, setSeccionActiva] = useState(seccionesVisibles[0]?.id);

  const seccion = seccionesVisibles.find((s) => s.id === seccionActiva);
  const navItems = seccionesVisibles.map((s) => ({ id: s.id, label: s.etiqueta, group: s.grupo }));

  return (
    <AppShell
      navItems={navItems}
      activeId={seccionActiva}
      onNavigate={setSeccionActiva}
      title={seccion?.etiqueta ?? "Portal interno"}
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

export default function App() {
  const { actor } = useAuth();
  return actor ? <Panel /> : <LoginCard />;
}
