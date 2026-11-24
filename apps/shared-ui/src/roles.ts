/**
 * Nombre legible por rol -- ronda de claridad de lenguaje (agosto 2026, ver
 * CLAUDE.md). Antes varias pantallas (Usuarios/Funcionalidades en
 * web-interno, "Mi cuenta" en las 3 apps vía `PerfilPropio`) mostraban el
 * identificador crudo del backend (ej. "admin_captacion") como si fuera la
 * etiqueta -- confuso para cualquiera que no conozca el nombre interno del
 * rol. Vive en `shared-ui` (no solo en web-interno) porque `PerfilPropio` lo
 * necesita para las 3 apps.
 */
export const NOMBRE_ROL: Record<string, string> = {
  admin_captacion: "Administrador de Captación",
  coordinador_operaciones: "Coordinador de Operaciones",
  coordinador_flota: "Coordinador de Flota",
  jefe_mantenimiento: "Jefe de Mantenimiento",
  admin_financiero: "Administrador Financiero",
  supervisor_cumplimiento: "Supervisor de Cumplimiento",
  responsable_plataforma: "Responsable de Plataforma",
  gerencia: "Gerencia",
  integracion_externa: "Integración Externa",
  admin_plataforma: "Administrador de Plataforma",
  admin_sistema: "Administrador del Sistema",
  conductor: "Conductor",
  pasajero: "Pasajero",
};

/** Nombre legible si existe en el mapa, o el identificador crudo como respaldo
 * (nunca deja la celda vacía si aparece un rol nuevo sin mapear todavía). */
export function nombreRol(rol: string): string {
  return NOMBRE_ROL[rol] ?? rol;
}
