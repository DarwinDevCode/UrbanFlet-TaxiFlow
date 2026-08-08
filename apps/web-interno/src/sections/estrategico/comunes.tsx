import type { ReactNode } from "react";

/**
 * Nota de limitación declarada por el backend en `metadata` (zona no
 * resuelta, tasa de cancelación no consolidable, capacitación inexistente,
 * km de vehículo ausente, cobertura parcial de canal, dataset mixto
 * 2021/2026...).
 *
 * Mismo criterio ya aplicado en el nivel táctico: la limitación se muestra
 * en la UI y el KPI afectado queda en "—"; **nunca** se fabrica el dato ni
 * se oculta la brecha.
 */
export function NotaLimitacion({ children }: { children: ReactNode }) {
  return (
    <p
      style={{
        margin: "var(--space-2) 0 0",
        fontSize: "var(--font-size-sm)",
        color: "var(--color-text-muted)",
      }}
    >
      {children}
    </p>
  );
}

/** Fila de filtros con el espaciado que ya usan los 9 paneles tácticos. */
export function FilaFiltros({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        display: "flex",
        gap: "var(--space-3)",
        flexWrap: "wrap",
        alignItems: "flex-end",
        marginBottom: "var(--space-4)",
      }}
    >
      {children}
    </div>
  );
}

/** Encabezado de tarjeta: título a la izquierda, `FuenteBadge` a la derecha. */
export function TituloTarjeta({ titulo, extra }: { titulo: string; extra?: ReactNode }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        gap: "var(--space-3)",
        marginBottom: "var(--space-3)",
      }}
    >
      <h3 style={{ margin: 0, fontSize: "var(--font-size-md)" }}>{titulo}</h3>
      {extra}
    </div>
  );
}
