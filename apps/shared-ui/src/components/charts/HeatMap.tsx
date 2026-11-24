/**
 * Mapa de calor simple (grid de celdas) para intensidad sobre 2 dimensiones
 * cruzadas -- ej. margen % por mes × franja. recharts no trae uno nativo, así
 * que es un grid CSS con escala secuencial de un solo tono (`color-mix()`
 * sobre `--chart-series-1`), sin librería nueva. Reconstruido (noviembre
 * 2026) tras la pérdida del archivo original, que nunca llegó a commitearse.
 */
export function HeatMap<T extends object>({
  datos,
  fila,
  columna,
  valor,
  formatoValor = (v: number) => String(v),
  vacio = "Sin datos para graficar.",
}: {
  datos: readonly T[];
  /** Campo que define la fila (eje Y). */
  fila: keyof T & string;
  /** Campo que define la columna (eje X). */
  columna: keyof T & string;
  /** Campo numérico que da la intensidad de la celda. */
  valor: keyof T & string;
  formatoValor?: (valor: number) => string;
  vacio?: string;
}) {
  if (datos.length === 0) {
    return <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>{vacio}</p>;
  }

  const filas = [...new Set(datos.map((d) => String(d[fila])))];
  const columnas = [...new Set(datos.map((d) => String(d[columna])))];
  const celdas = new Map<string, number>();
  for (const d of datos) {
    const v = Number(d[valor]);
    if (!Number.isNaN(v)) celdas.set(`${String(d[fila])}|${String(d[columna])}`, v);
  }
  const valores = [...celdas.values()];
  const min = Math.min(...valores);
  const max = Math.max(...valores);
  const intensidad = (v: number) => (max === min ? 60 : 12 + ((v - min) / (max - min)) * 76);

  return (
    <div style={{ overflowX: "auto" }}>
      <div
        role="table"
        style={{
          display: "grid",
          gridTemplateColumns: `minmax(90px, auto) repeat(${columnas.length}, minmax(72px, 1fr))`,
          gap: 2,
          fontSize: "var(--font-size-sm)",
        }}
      >
        <div />
        {columnas.map((c) => (
          <div key={c} style={{ padding: "var(--space-1)", color: "var(--color-text-muted)", textAlign: "center" }}>
            {c}
          </div>
        ))}
        {filas.map((f) => (
          <div key={f} role="row" style={{ display: "contents" }}>
            <div style={{ padding: "var(--space-1)", color: "var(--color-text-muted)", alignSelf: "center" }}>{f}</div>
            {columnas.map((c) => {
              const v = celdas.get(`${f}|${c}`);
              const pctTinta = v == null ? 0 : intensidad(v);
              return (
                <div
                  key={c}
                  title={v == null ? "Sin dato" : `${f} · ${c}: ${formatoValor(v)}`}
                  style={{
                    padding: "var(--space-2) var(--space-1)",
                    textAlign: "center",
                    fontVariantNumeric: "tabular-nums",
                    background:
                      v == null
                        ? "var(--color-bg)"
                        : `color-mix(in srgb, var(--chart-series-1) ${pctTinta}%, var(--color-surface))`,
                    color: pctTinta > 55 ? "#fff" : "var(--color-text)",
                  }}
                >
                  {v == null ? "—" : formatoValor(v)}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
