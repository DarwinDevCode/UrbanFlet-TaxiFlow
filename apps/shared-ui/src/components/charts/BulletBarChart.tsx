import { Bar, BarChart, CartesianGrid, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { seriesColor } from "./palette";

/**
 * Barras horizontales con banda de umbral (estilo bullet): zona de peligro
 * debajo de `advertencia`, de advertencia hasta `bueno`, y buena por encima.
 * Sirve también como ranking horizontal simple si no se pasan umbrales.
 * Reconstruido (noviembre 2026) tras la pérdida del archivo original, que
 * nunca llegó a commitearse.
 */
export function BulletBarChart<T extends object>({
  datos,
  categoria,
  valor,
  etiquetaValor = "Valor",
  umbrales,
  maximo,
  formatoValor = (v: number) => String(v),
  alto,
  vacio = "Sin datos para graficar.",
}: {
  datos: readonly T[];
  categoria: keyof T & string;
  valor: keyof T & string;
  etiquetaValor?: string;
  /** Límites de las bandas, en la misma unidad que `valor`. */
  umbrales?: { advertencia: number; bueno: number };
  /** Extremo del eje; por defecto el mayor valor de los datos. */
  maximo?: number;
  formatoValor?: (valor: number) => string;
  alto?: number;
  vacio?: string;
}) {
  if (datos.length === 0) {
    return <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>{vacio}</p>;
  }
  const tope = maximo ?? Math.max(...datos.map((d) => Number(d[valor]) || 0), umbrales?.bueno ?? 0);
  const altoReal = alto ?? Math.max(120, datos.length * 44 + 40);

  return (
    <ResponsiveContainer width="100%" height={altoReal}>
      <BarChart data={datos as T[]} layout="vertical" margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
        {umbrales && (
          <>
            <ReferenceArea x1={0} x2={umbrales.advertencia} fill="var(--status-critical)" fillOpacity={0.1} />
            <ReferenceArea x1={umbrales.advertencia} x2={umbrales.bueno} fill="var(--status-warning)" fillOpacity={0.12} />
            <ReferenceArea x1={umbrales.bueno} x2={tope} fill="var(--status-good)" fillOpacity={0.1} />
          </>
        )}
        <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" horizontal={false} />
        <XAxis
          type="number"
          domain={[0, tope]}
          tick={{ fill: "var(--chart-muted)", fontSize: 12 }}
          axisLine={{ stroke: "var(--chart-axis)" }}
          tickLine={false}
          tickFormatter={(v) => formatoValor(Number(v))}
        />
        <YAxis
          type="category"
          dataKey={categoria}
          tick={{ fill: "var(--chart-muted)", fontSize: 12 }}
          axisLine={false}
          tickLine={false}
          width={140}
        />
        <Tooltip
          formatter={(v: number) => [formatoValor(v), etiquetaValor]}
          contentStyle={{
            background: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            fontSize: "var(--font-size-sm)",
          }}
          cursor={{ fill: "var(--color-bg)" }}
        />
        <Bar dataKey={valor} name={etiquetaValor} fill={seriesColor(0)} maxBarSize={22} />
      </BarChart>
    </ResponsiveContainer>
  );
}
