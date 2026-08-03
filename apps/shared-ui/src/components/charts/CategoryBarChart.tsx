import {
  Bar,
  BarChart as RBarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { seriesColor } from "./palette";

export interface CategoryBarSeries {
  /** Clave del campo en cada fila de `datos` que esta serie grafica. */
  key: string;
  /** Etiqueta legible para leyenda/tooltip. */
  label: string;
}

/**
 * Barras verticales para comparación entre categorías (skill dataviz:
 * "barras para comparación entre categorías"). Una sola serie = una barra
 * por categoría en azul (`--chart-series-1`); varias series = una barra por
 * serie, coloreadas en el orden categórico fijo, con leyenda.
 */
export function CategoryBarChart<T extends object>({
  datos,
  categoria,
  series,
  formatoValor = (v: number) => String(v),
  alto = 260,
  vacio = "Sin datos para graficar.",
}: {
  datos: readonly T[];
  /** Nombre del campo categórico (eje X). */
  categoria: keyof T & string;
  series: CategoryBarSeries[];
  formatoValor?: (valor: number) => string;
  alto?: number;
  vacio?: string;
}) {
  if (datos.length === 0) {
    return <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>{vacio}</p>;
  }

  return (
    <ResponsiveContainer width="100%" height={alto}>
      <RBarChart data={datos as T[]} margin={{ top: 8, right: 8, left: 0, bottom: 8 }} barCategoryGap="24%">
        <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" vertical={false} />
        <XAxis
          dataKey={categoria}
          tick={{ fill: "var(--chart-muted)", fontSize: 12 }}
          axisLine={{ stroke: "var(--chart-axis)" }}
          tickLine={false}
          interval={0}
          angle={datos.length > 6 ? -20 : 0}
          textAnchor={datos.length > 6 ? "end" : "middle"}
          height={datos.length > 6 ? 56 : 30}
        />
        <YAxis
          tick={{ fill: "var(--chart-muted)", fontSize: 12 }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => formatoValor(Number(v))}
          width={56}
        />
        <Tooltip
          formatter={(value: number, name: string) => [formatoValor(value), name]}
          contentStyle={{
            background: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-sm)",
            fontSize: "var(--font-size-sm)",
          }}
          cursor={{ fill: "var(--color-bg)" }}
        />
        {series.length > 1 && <Legend wrapperStyle={{ fontSize: "var(--font-size-sm)" }} />}
        {series.map((s, i) => (
          <Bar key={s.key} dataKey={s.key} name={s.label} fill={seriesColor(i)} radius={[4, 4, 0, 0]} maxBarSize={48} />
        ))}
      </RBarChart>
    </ResponsiveContainer>
  );
}
