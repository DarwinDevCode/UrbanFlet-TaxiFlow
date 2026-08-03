import type { PropsWithChildren } from "react";

type KpiTono = "exito" | "advertencia" | "serio" | "peligro";

const TONO_COLOR: Record<KpiTono, string> = {
  exito: "var(--status-good)",
  advertencia: "var(--status-warning)",
  serio: "var(--status-serious)",
  peligro: "var(--status-critical)",
};

export function KpiCard({
  etiqueta,
  valor,
  tono,
}: {
  etiqueta: string;
  valor: string;
  /** Color con significado de estado — omitir para un KPI neutro (informativo). */
  tono?: KpiTono;
}) {
  const colorValor = tono ? TONO_COLOR[tono] : "var(--color-text)";
  return (
    <div
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius-lg)",
        boxShadow: "var(--shadow-sm)",
        padding: "var(--space-4) var(--space-5)",
        flex: "1 1 200px",
        minWidth: "200px",
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-2)",
      }}
    >
      <p
        style={{
          margin: 0,
          fontSize: "var(--font-size-sm)",
          fontWeight: 500,
          color: "var(--color-text-muted)",
          textTransform: "uppercase",
          letterSpacing: "0.03em",
        }}
      >
        {etiqueta}
      </p>
      <p
        style={{
          margin: 0,
          fontSize: "var(--font-size-2xl)",
          fontWeight: 700,
          lineHeight: 1.1,
          color: colorValor,
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {valor}
      </p>
    </div>
  );
}

export function KpiRow({ children }: PropsWithChildren) {
  return <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-4)" }}>{children}</div>;
}
