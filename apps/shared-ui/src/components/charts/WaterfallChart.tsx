import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export interface PasoCascada {
  etiqueta: string;
  /** Monto del paso. Negativo = resta (se dibuja hacia abajo). */
  valor: number;
  /** `true` para los totales (barra desde 0, no flotante). */
  total?: boolean;
}

/**
 * Cascada (Bruto → −Comisión → Neto) con barras flotantes de recharts: cada
 * paso se dibuja como una barra apilada cuyo primer tramo es transparente
 * (la base acumulada). Reconstruido (noviembre 2026) tras la pérdida del
 * archivo original, que nunca llegó a commitearse.
 */
export function WaterfallChart({
  pasos,
  formatoValor = (v: number) => String(v),
  alto = 240,
  vacio = "Sin datos para graficar.",
}: {
  pasos: readonly PasoCascada[];
  formatoValor?: (valor: number) => string;
  alto?: number;
  vacio?: string;
}) {
  if (pasos.length === 0) {
    return <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>{vacio}</p>;
  }

  let acumulado = 0;
  const datos = pasos.map((p) => {
    if (p.total) {
      acumulado = p.valor;
      return { etiqueta: p.etiqueta, base: 0, tramo: p.valor, real: p.valor, tipo: "total" as const };
    }
    const inicio = acumulado;
    acumulado += p.valor;
    return {
      etiqueta: p.etiqueta,
      base: Math.min(inicio, acumulado),
      tramo: Math.abs(p.valor),
      real: p.valor,
      tipo: p.valor < 0 ? ("resta" as const) : ("suma" as const),
    };
  });

  const color = { total: "var(--chart-series-1)", resta: "var(--status-critical)", suma: "var(--status-good)" };

  return (
    <ResponsiveContainer width="100%" height={alto}>
      <BarChart data={datos} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" vertical={false} />
        <XAxis dataKey="etiqueta" tick={{ fill: "var(--chart-muted)", fontSize: 12 }} axisLine={{ stroke: "var(--chart-axis)" }} tickLine={false} />
        <YAxis
          tick={{ fill: "var(--chart-muted)", fontSize: 12 }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => formatoValor(Number(v))}
          width={64}
        />
        <Tooltip
          formatter={(_v: number, _n: string, item) => [formatoValor(Number(item.payload.real)), item.payload.etiqueta]}
          contentStyle={{
            background: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            fontSize: "var(--font-size-sm)",
          }}
          cursor={{ fill: "var(--color-bg)" }}
        />
        <Bar dataKey="base" stackId="c" fill="transparent" isAnimationActive={false} />
        <Bar dataKey="tramo" stackId="c" maxBarSize={56}>
          {datos.map((d) => (
            <Cell key={d.etiqueta} fill={color[d.tipo]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
