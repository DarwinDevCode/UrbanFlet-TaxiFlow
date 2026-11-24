import type { PropsWithChildren, ReactNode } from "react";
import { Button } from "./Button";

export type ModoPanel = "consulta" | "edicion" | "nuevo";

const etiquetaModo: Record<ModoPanel, string> = {
  consulta: "Modo: Consulta",
  edicion: "Modo: Edición",
  nuevo: "Modo: Nuevo registro",
};

// Mismo tratamiento de chip (fondo suave + texto semántico) que Badge, ver
// CLAUDE.md -- este indicador es propio de DetailPanel, no reutiliza Badge
// directamente porque sus 3 estados (consulta/edición/nuevo) no mapean a
// los tonos de BadgeTono.
const estiloModo: Record<ModoPanel, { color: string; background: string }> = {
  consulta: { color: "var(--color-text-muted)", background: "var(--color-neutral-bg)" },
  edicion: { color: "var(--color-warning)", background: "var(--color-warning-bg)" },
  nuevo: { color: "var(--color-accent)", background: "var(--color-warning-bg)" },
};

interface DetailPanelProps extends PropsWithChildren {
  titulo: string;
  modo: ModoPanel;
  onAceptar?: () => void;
  onSalir: () => void;
  aceptarLabel?: string;
  aceptarDisabled?: boolean;
  aceptarLoading?: boolean;
  /** Acciones contextuales adicionales (p.ej. Tomar, Cerrar orden, Anular) que
   * se muestran junto a Aceptar/Salir sin romper la posición fija de esos dos. */
  accionesExtra?: ReactNode;
}

/**
 * Panel de detalle más grande que se abre al seleccionar una fila de la
 * lista. Muestra toda la información relevante de la entidad (via children),
 * un indicador explícito de en qué modo está el panel (consulta / edición /
 * nuevo registro) y los botones Aceptar/Salir en posición fija.
 */
export function DetailPanel({
  titulo,
  modo,
  onAceptar,
  onSalir,
  aceptarLabel = "Aceptar",
  aceptarDisabled,
  aceptarLoading,
  accionesExtra,
  children,
}: DetailPanelProps) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.4)",
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "center",
        padding: "var(--space-5)",
        overflowY: "auto",
        zIndex: "var(--z-modal)",
      }}
    >
      <div
        style={{
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--radius-lg)",
          boxShadow: "var(--shadow-sm)",
          padding: "var(--space-5)",
          width: "min(920px, 100%)",
          maxHeight: "calc(100vh - var(--space-5) * 2)",
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          gap: "var(--space-4)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "var(--space-3)" }}>
          <h2 style={{ margin: 0, fontSize: "var(--font-size-lg)" }}>{titulo}</h2>
          <span
            style={{
              display: "inline-block",
              padding: "2px 10px",
              borderRadius: "999px",
              fontSize: "var(--font-size-sm)",
              fontWeight: 600,
              whiteSpace: "nowrap",
              ...estiloModo[modo],
            }}
          >
            {etiquetaModo[modo]}
          </span>
        </div>

        <div>{children}</div>

        <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap", justifyContent: "flex-end" }}>
          {accionesExtra}
          {onAceptar && (
            <div style={{ minWidth: 140 }}>
              <Button onClick={onAceptar} disabled={aceptarDisabled} loading={aceptarLoading}>
                {aceptarLabel}
              </Button>
            </div>
          )}
          <div style={{ minWidth: 140 }}>
            <Button variant="secondary" onClick={onSalir}>
              Salir
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

/** Fila etiqueta/valor reutilizable para el cuerpo de un DetailPanel. */
export function DetailField({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <span style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>{label}</span>
      <span>{value}</span>
    </div>
  );
}
