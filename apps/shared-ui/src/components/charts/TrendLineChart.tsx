import {
  CartesianGrid,
  Legend,
  Line,
  LineChart as RLineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { seriesColor } from "./palette";

export interface TrendLineSeries {
  key: string;
  label: string;
}

/**
 * Línea(s) para tendencia en el tiempo (skill dataviz: "líneas para
 * tendencia"). Una serie = una línea azul; varias series (p.ej. una por
 * tipo de documento) = una línea por serie en el orden categórico fijo, con
 * leyenda siempre visible desde 2 series.
 */
export function TrendLineChart<T extends object>({
  datos,
  eje,
  series,
  formatoValor = (v: number) => String(v),
  alto = 260,
  vacio = "Sin historial publicado todavía.",
}: {
  datos: readonly T[];
  /** Nombre del campo de eje X (fecha/periodo). */
  eje: keyof T & string;
  series: TrendLineSeries[];
  formatoValor?: (valor: number) => string;
  alto?: number;
  vacio?: string;
}) {
  if (datos.length === 0) {
    return <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>{vacio}</p>;
  }

  return (
    <ResponsiveContainer width="100%" height={alto}>
      <RLineChart data={datos as T[]} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" vertical={false} />
        <XAxis
          dataKey={eje}
          tick={{ fill: "var(--chart-muted)", fontSize: 12 }}
          axisLine={{ stroke: "var(--chart-axis)" }}
          tickLine={false}
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
        />
        {series.length > 1 && <Legend wrapperStyle={{ fontSize: "var(--font-size-sm)" }} />}
        {series.map((s, i) => (
          <Line
            key={s.key}
            type="monotone"
            dataKey={s.key}
            name={s.label}
            stroke={seriesColor(i)}
            strokeWidth={2}
            dot={{ r: 3, fill: seriesColor(i), strokeWidth: 0 }}
            activeDot={{ r: 5 }}
          />
        ))}
      </RLineChart>
    </ResponsiveContainer>
  );
}
