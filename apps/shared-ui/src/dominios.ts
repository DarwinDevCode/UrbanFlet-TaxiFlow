/**
 * Nombre legible por dominio de proceso de datos -- segundo rediseño visual
 * (v2), mismo criterio que `roles.ts::nombreRol`. Antes `PanelPlataforma`
 * (táctico) y `PanelCapacidades` (estratégico) mostraban el `dag_id` crudo
 * del backend (ej. "dag_viajes_core"), o como mucho le recortaban a mano el
 * prefijo/sufijo ("viajes_core") -- confuso para cualquiera que no conozca
 * el nombre interno del job. Vive en `shared-ui` porque los 2 niveles lo
 * necesitan. Los 7 valores son los `dag_id` reales confirmados contra
 * ClickHouse (`SELECT DISTINCT dag_id FROM corridas`).
 */
export const NOMBRE_DOMINIO: Record<string, string> = {
  dag_captacion_gold: "Captación",
  dag_cumplimiento_gold: "Cumplimiento",
  dag_finanzas_gold: "Finanzas",
  dag_flota_gold: "Flota",
  dag_historico_nyc: "Histórico (dataset de calibración)",
  dag_mantenimiento_gold: "Mantenimiento",
  dag_viajes_core: "Viajes",
};

/** Nombre legible si existe en el mapa, o el identificador crudo como
 * respaldo (nunca deja la celda vacía si aparece un dominio nuevo sin
 * mapear todavía). */
export function nombreDominio(dagId: string): string {
  return NOMBRE_DOMINIO[dagId] ?? dagId;
}
