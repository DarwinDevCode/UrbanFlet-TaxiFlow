/**
 * Formateadores compartidos por los 9 dashboards del nivel estratégico.
 *
 * Convención confirmada contra las respuestas reales de los 9 endpoints de
 * la Fase 3 (`git show c0a123d`): todo campo `pct_*` / `margen_pct` /
 * `share_*` viaja como **fracción 0-1**, mientras que todo campo
 * `variacion_*_pct` viaja ya en **puntos porcentuales** (p. ej. `2514.29`
 * significa +2514,29%). Mezclarlos es el error fácil de este nivel — de ahí
 * dos helpers distintos en vez de uno solo.
 */

/** Fracción 0-1 → porcentaje legible. `null` → "—" (nunca un 0 fabricado). */
export function pct(valor: number | null | undefined, decimales = 1): string {
  if (valor == null || Number.isNaN(valor)) return "—";
  return `${(valor * 100).toFixed(decimales)}%`;
}

/** Variación ya expresada en puntos porcentuales, con signo explícito. */
export function variacion(valor: number | null | undefined, decimales = 1): string {
  if (valor == null || Number.isNaN(valor)) return "—";
  return `${valor > 0 ? "+" : ""}${valor.toFixed(decimales)}%`;
}

export function moneda(valor: number | null | undefined, decimales = 2): string {
  if (valor == null || Number.isNaN(valor)) return "—";
  return `$${valor.toLocaleString("es-EC", { minimumFractionDigits: decimales, maximumFractionDigits: decimales })}`;
}

export function entero(valor: number | null | undefined): string {
  if (valor == null || Number.isNaN(valor)) return "—";
  return valor.toLocaleString("es-EC");
}

export function segundos(valor: number | null | undefined): string {
  if (valor == null || Number.isNaN(valor)) return "—";
  return `${valor.toFixed(1)}s`;
}

/**
 * Tono de estado para una variación: mejor/peor según si subir es bueno.
 * Devuelve `undefined` (KPI neutro) cuando no hay dato o el cambio es nulo,
 * en vez de pintar de verde un "sin información".
 */
export function tonoVariacion(
  valor: number | null | undefined,
  { subirEsBueno }: { subirEsBueno: boolean },
): "exito" | "peligro" | undefined {
  if (valor == null || valor === 0) return undefined;
  const bueno = subirEsBueno ? valor > 0 : valor < 0;
  return bueno ? "exito" : "peligro";
}

/** Opciones del filtro de ventana temporal, compartido por los 8 paneles. */
export const OPCIONES_VENTANA = [
  { value: "3", label: "Últimos 3" },
  { value: "6", label: "Últimos 6" },
  { value: "12", label: "Últimos 12" },
  { value: "24", label: "Últimos 24" },
];
