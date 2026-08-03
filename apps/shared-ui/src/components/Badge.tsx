type BadgeTono = "neutral" | "exito" | "advertencia" | "peligro";

const tonoColor: Record<BadgeTono, string> = {
  neutral: "var(--color-text-muted)",
  exito: "var(--color-success)",
  advertencia: "var(--color-warning)",
  peligro: "var(--color-danger)",
};

export function Badge({ texto, tono = "neutral" }: { texto: string; tono?: BadgeTono }) {
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 10px",
        borderRadius: "999px",
        fontSize: "var(--font-size-sm)",
        fontWeight: 600,
        color: "#ffffff",
        background: tonoColor[tono],
        whiteSpace: "nowrap",
      }}
    >
      {texto}
    </span>
  );
}
