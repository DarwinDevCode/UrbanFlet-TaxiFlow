/** Referencia visual de auditoría: de dónde sale cada informe de un dashboard táctico. */
export function FuenteBadge({ tipo }: { tipo: "simple" | "compuesto" }) {
  const texto = tipo === "simple" ? "Simple · MongoDB" : "Compuesto · ClickHouse";
  const color = tipo === "simple" ? "var(--color-text-muted)" : "var(--color-accent)";
  return (
    <span
      style={{
        display: "inline-block",
        fontSize: "var(--font-size-sm)",
        fontWeight: 600,
        color,
        border: `1px solid ${color}`,
        borderRadius: "var(--radius-sm)",
        padding: "1px 8px",
      }}
    >
      {texto}
    </span>
  );
}
