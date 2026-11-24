/**
 * Catálogo de tipos de notificación -- fuente única para etiqueta legible,
 * usada tanto por `NotificacionesBell` (panel desplegable) como por
 * `SeccionNotificaciones` (sección completa), para que un mismo `tipo`
 * nunca muestre dos textos distintos según dónde se lo mire.
 *
 * Confirmado contra el código real antes de escribir esto (Fase 0 de la
 * ronda que agregó la sección completa) -- son los 13 `tipo` que
 * `dispatcher.notify_user(...)` dispara hoy en todo el backend (grep de
 * cada call site, no una lista inventada). `DOCUMENTO_VENCIDO`/
 * `DOCUMENTO_POR_VENCER` faltaban en el `ETIQUETA_POR_TIPO` original de la
 * campana (se mostraban con el enum crudo) -- corregido acá de una vez para
 * los dos consumidores.
 */
export interface NotificacionOut {
  id: string;
  tipo: string;
  categoria: string;
  payload: Record<string, unknown>;
  ts: string;
  leida: boolean;
}

export const ETIQUETA_POR_TIPO: Record<string, string> = {
  NUEVA_SOLICITUD: "Nueva solicitud de conductor",
  SOLICITUD_DECISION: "Tu solicitud tuvo una decisión",
  DOCUMENTO_VENCIDO: "Un documento venció",
  DOCUMENTO_POR_VENCER: "Un documento está por vencer",
  RENOVACION_DOCUMENTO_DECISION: "Renovación de documento resuelta",
  ORDEN_MANTENIMIENTO_REGISTRADA: "Nueva orden de mantenimiento",
  ORDEN_MANTENIMIENTO_CERRADA: "Orden de mantenimiento cerrada",
  ALERTA_SEGURIDAD: "Alerta de seguridad",
  VIAJE_ASIGNADO: "Se asignó un conductor a tu viaje",
  CONDUCTOR_EN_CAMINO: "El conductor va en camino",
  CONDUCTOR_LLEGO: "El conductor llegó",
  VIAJE_INICIADO: "El viaje comenzó",
  VIAJE_FINALIZADO: "El viaje finalizó",
  VIAJE_CANCELADO_CONDUCTOR: "El conductor canceló el viaje",
};

/**
 * `ALERTA_SEGURIDAD` es un solo `tipo` en la bandeja (ver
 * `notificaciones/service.py::disparar_alerta`), pero conflacia 5 orígenes
 * reales muy distintos (`payload.tipo_alerta`) con destinatarios y
 * significado propios -- esta segunda etiqueta desambigua para mostrar/
 * enrutar cada uno por separado sin tocar el `tipo` que persiste el backend.
 */
export const ETIQUETA_POR_TIPO_ALERTA: Record<string, string> = {
  denegaciones_rbac: "5 accesos denegados seguidos",
  gps_spoofing: "Posible salto de posición GPS",
  pipeline_fallido: "Corrida de pipeline fallida",
  reporte_falla: "Reporte de falla de un vehículo",
  incidencia_operativa: "Incidencia operativa en un viaje",
};

/** Etiqueta efectiva a mostrar: para `ALERTA_SEGURIDAD` desambigua por
 * `payload.tipo_alerta`; para el resto, usa `ETIQUETA_POR_TIPO` tal cual. */
export function etiquetaNotificacion(n: Pick<NotificacionOut, "tipo" | "payload">): string {
  if (n.tipo === "ALERTA_SEGURIDAD") {
    const sub = typeof n.payload.tipo_alerta === "string" ? n.payload.tipo_alerta : undefined;
    return (sub && ETIQUETA_POR_TIPO_ALERTA[sub]) ?? ETIQUETA_POR_TIPO.ALERTA_SEGURIDAD;
  }
  return ETIQUETA_POR_TIPO[n.tipo] ?? n.tipo;
}

// ---------------------------------------------------------------------------
// Vista legible del detalle -- reemplaza el JSON crudo del `payload`.
//
// No existe hoy ningún componente en el sistema que ya haga esto para
// `datos_previos`/`datos_posteriores` (verificado antes de escribir esto:
// `AuditoriaAdmin.tsx`, el único lugar que muestra ese detalle, también usa
// `JSON.stringify` dentro de un `<pre>` -- el mismo problema, no un patrón a
// copiar). Lo que SÍ es un patrón real y reutilizable en todo el proyecto es
// `DetailField` (etiqueta/valor, usado en cada `DetailPanel` del sistema) --
// acá se arma la lista de campos por tipo para que `SeccionNotificaciones`
// los pinte con ese mismo componente.
// ---------------------------------------------------------------------------

export interface CampoLegible {
  etiqueta: string;
  valor: string;
}

// Bitácora de revisión (2026-08-26, hallazgo #4): exportado -- antes vivía
// sin `export`, así que `web-conductor/App.tsx` tenía su propia copia
// duplicada del mismo diccionario en vez de importar este.
export const ETIQUETA_TIPO_DOCUMENTO: Record<string, string> = {
  LICENCIA_CONDUCIR: "Licencia de conducir",
  MATRICULA_VEHICULAR: "Matrícula vehicular",
};

/** Nombre legible de un tipo de documento, con el mismo criterio de
 * `nombreRol()`/`nombreDominio()`: si el tipo no está en el diccionario
 * (un tipo nuevo del catálogo todavía no mapeado), se muestra tal cual en
 * vez de romper. */
export function nombreTipoDocumento(tipo: string): string {
  return ETIQUETA_TIPO_DOCUMENTO[tipo] ?? tipo;
}

const ETIQUETA_DECISION: Record<string, string> = {
  APROBADA: "Aprobada",
  RECHAZADA: "Rechazada",
  OBSERVADA: "Observada",
  EN_VERIFICACION: "En verificación",
};

const ETIQUETA_TIPO_ORDEN: Record<string, string> = {
  PREVENTIVA: "Preventiva",
  CORRECTIVA: "Correctiva",
};

function texto(v: unknown): string {
  return v === null || v === undefined ? "—" : String(v);
}

/**
 * `ALERTA_SEGURIDAD` no trae campos estructurados propios -- todo viaja en
 * un `motivo` de texto libre (`payload = {tipo_alerta, motivo}`, ver
 * `notificaciones/service.py::disparar_alerta`). Cada `tipo_alerta` real
 * arma su `motivo` con un formato fijo (confirmado leyendo cada call site
 * real, no adivinado):
 * - reporte_falla / incidencia_operativa (`reportes_falla/service.py`):
 *   `"Vehículo {placa}: {tipo_falla}"`.
 * - gps_spoofing (`flota/service.py`):
 *   `"Posible GPS spoofing: vehículo {id}, salto de {km} km entre reportes consecutivos"`.
 * - denegaciones_rbac (`core/rbac.py`):
 *   `"Sesión de {usuario_id} suspendida por accesos denegados repetidos"`.
 * Se parsean esos formatos reales en campos con etiqueta -- si el motivo no
 * calza con el patrón esperado (dato viejo, u origen no reconocido como
 * `pipeline_fallido`, que hoy no dispara ninguno real, ver el mismo
 * service), se degrada a una sola línea "Motivo: <texto>" en vez de fallar
 * o mostrar JSON.
 */
function camposAlertaSeguridad(payload: Record<string, unknown>): CampoLegible[] {
  const tipoAlerta = typeof payload.tipo_alerta === "string" ? payload.tipo_alerta : undefined;
  const motivo = typeof payload.motivo === "string" ? payload.motivo : "";

  if (tipoAlerta === "reporte_falla" || tipoAlerta === "incidencia_operativa") {
    const m = motivo.match(/^Vehículo ([^:]+): (.+)$/);
    if (m) return [{ etiqueta: "Vehículo", valor: m[1] }, { etiqueta: "Tipo de incidencia", valor: m[2] }];
  }
  if (tipoAlerta === "gps_spoofing") {
    const m = motivo.match(/^Posible GPS spoofing: vehículo ([^,]+), salto de ([\d.]+) km entre reportes consecutivos$/);
    if (m) {
      return [
        { etiqueta: "Vehículo (identificador)", valor: m[1] },
        { etiqueta: "Salto de posición detectado", valor: `${m[2]} km entre 2 reportes seguidos` },
      ];
    }
  }
  if (tipoAlerta === "denegaciones_rbac") {
    const m = motivo.match(/^Sesión de (.+) suspendida por accesos denegados repetidos$/);
    if (m) {
      return [
        { etiqueta: "Cuenta suspendida", valor: m[1] },
        { etiqueta: "Motivo", valor: "5 accesos denegados seguidos en la ventana configurada" },
      ];
    }
  }
  return motivo ? [{ etiqueta: "Motivo", valor: motivo }] : [];
}

/** Campos legibles del `payload`, por tipo real -- mapa completo de los 13
 * tipos del catálogo (Fase 0 de la ronda que agregó la sección completa).
 * Nunca devuelve el payload crudo: un tipo sin campos reconocidos devuelve
 * lista vacía (el detalle simplemente no muestra nada extra, en vez de
 * fabricar una etiqueta técnica). */
export function camposLegibles(n: Pick<NotificacionOut, "tipo" | "payload">): CampoLegible[] {
  const p = n.payload;
  switch (n.tipo) {
    case "NUEVA_SOLICITUD":
      return [{ etiqueta: "Solicitud", valor: texto(p.solicitud_id) }];
    case "SOLICITUD_DECISION": {
      const estado = typeof p.estado === "string" ? p.estado : undefined;
      const campos: CampoLegible[] = [
        { etiqueta: "Resultado", valor: (estado && ETIQUETA_DECISION[estado]) ?? texto(p.estado) },
      ];
      if (p.motivo) campos.push({ etiqueta: "Motivo", valor: texto(p.motivo) });
      return campos;
    }
    case "DOCUMENTO_VENCIDO": {
      const tipoDoc = typeof p.tipo === "string" ? p.tipo : undefined;
      return [
        { etiqueta: "Documento", valor: texto(p.documento_id) },
        { etiqueta: "Tipo de documento", valor: (tipoDoc && ETIQUETA_TIPO_DOCUMENTO[tipoDoc]) ?? texto(p.tipo) },
      ];
    }
    case "DOCUMENTO_POR_VENCER":
      return [
        { etiqueta: "Documento", valor: texto(p.documento_id) },
        { etiqueta: "Días para vencer", valor: texto(p.dias_para_vencer) },
      ];
    case "RENOVACION_DOCUMENTO_DECISION": {
      const campos: CampoLegible[] = [
        { etiqueta: "Documento", valor: texto(p.documento_id) },
        { etiqueta: "Resultado", valor: p.aprobado ? "Aprobada" : "Observada" },
      ];
      if (p.motivo) campos.push({ etiqueta: "Motivo", valor: texto(p.motivo) });
      return campos;
    }
    case "ORDEN_MANTENIMIENTO_REGISTRADA": {
      const tipoOrden = typeof p.tipo === "string" ? p.tipo : undefined;
      return [
        { etiqueta: "Orden", valor: texto(p.orden_id) },
        { etiqueta: "Tipo de orden", valor: (tipoOrden && ETIQUETA_TIPO_ORDEN[tipoOrden]) ?? texto(p.tipo) },
      ];
    }
    case "ORDEN_MANTENIMIENTO_CERRADA":
      return [
        { etiqueta: "Orden", valor: texto(p.orden_id) },
        { etiqueta: "Costo total", valor: typeof p.costo_total === "number" ? `$${p.costo_total.toFixed(2)}` : texto(p.costo_total) },
      ];
    case "ALERTA_SEGURIDAD":
      return camposAlertaSeguridad(p);
    case "VIAJE_ASIGNADO":
    case "CONDUCTOR_EN_CAMINO":
    case "CONDUCTOR_LLEGO":
    case "VIAJE_INICIADO":
    case "VIAJE_FINALIZADO":
    case "VIAJE_CANCELADO_CONDUCTOR":
      return [{ etiqueta: "Viaje", valor: texto(p.viaje_id) }];
    default:
      return [];
  }
}
