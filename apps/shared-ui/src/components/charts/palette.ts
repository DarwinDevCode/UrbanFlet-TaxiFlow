/** Orden categórico fijo (skill dataviz) — nunca reordenar por serie individual. */
export const CHART_SERIES = [
  "var(--chart-series-1)",
  "var(--chart-series-2)",
  "var(--chart-series-3)",
  "var(--chart-series-4)",
  "var(--chart-series-5)",
  "var(--chart-series-6)",
  "var(--chart-series-7)",
  "var(--chart-series-8)",
];

export function seriesColor(index: number): string {
  return CHART_SERIES[index % CHART_SERIES.length];
}
