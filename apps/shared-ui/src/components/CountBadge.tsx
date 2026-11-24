/**
 * Indicador circular de conteo (ej. no leídas) -- extraído de
 * `NotificacionesBell` para que la campana y la entrada de sidebar
 * correspondiente (`AppShell`) usen literalmente el MISMO estilo, en vez de
 * dos implementaciones visuales distintas para el mismo concepto.
 */
export function CountBadge({ valor }: { valor: number }) {
  if (valor <= 0) return null;
  return (
    <span
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        minWidth: 16,
        height: 16,
        padding: "0 3px",
        borderRadius: "999px",
        background: "var(--color-danger)",
        color: "#fff",
        fontSize: "0.65rem",
        fontWeight: 700,
        lineHeight: 1,
      }}
    >
      {valor > 9 ? "9+" : valor}
    </span>
  );
}
