import type { ParadaRiel } from "./components/Riel";

/**
 * LOS TRAYECTOS DEL DOMINIO — Sistema Riel.
 *
 * Un solo lugar donde se declara, para cada objeto del negocio, cuáles son
 * sus paradas y en cuál cae cada estado del backend. Sin esto, cada
 * pantalla tendría que inventar su propio mapeo y el riel dejaría de
 * significar lo mismo en dos lugares distintos.
 *
 * Dos reglas que sostienen la coherencia del sistema:
 *
 * - **El nombre de la parada es el que lee una persona**, nunca el enum
 *   crudo. `EN_VERIFICACION` se muestra como "En verificación". Ese es el
 *   único lugar del sistema donde se traduce.
 * - **Los desvíos no inventan una parada nueva**: una solicitud observada
 *   sigue estando en la parada de verificación, marcada como adversa. El
 *   trayecto conserva su longitud, así que dos filas de la misma tabla se
 *   pueden comparar de un vistazo.
 */

export interface Trayecto {
  paradas: ParadaRiel[];
  /** Índice de la parada donde cae el estado. Se llama `actual` y no
   * `indice` para que un trayecto se pueda pasar entero al riel con
   * `<Riel {...trayectoOrden(estado)} />`, sin que cada pantalla tenga que
   * mapear campos a mano. */
  actual: number;
}

function resolver(paradas: ParadaRiel[], mapa: Record<string, number>, estado: string): Trayecto {
  const indice = mapa[estado];
  return { paradas, actual: indice ?? 0 };
}

/* ── Solicitud de socio conductor ───────────────────────────────────────
   Enviada → En verificación → Aprobada. "Observada" es la parada de
   verificación en estado adverso (el postulante debe corregir); "Rechazada"
   es el final adverso del trayecto. */
const PARADAS_SOLICITUD: ParadaRiel[] = [
  { nombre: "Enviada" },
  { nombre: "En verificación" },
  { nombre: "Aprobada" },
];

export function trayectoSolicitud(estado: string): Trayecto {
  if (estado === "OBSERVADA") {
    return {
      paradas: [PARADAS_SOLICITUD[0], { nombre: "Observada", adverso: true }, PARADAS_SOLICITUD[2]],
      actual: 1,
    };
  }
  if (estado === "RECHAZADA") {
    return {
      paradas: [PARADAS_SOLICITUD[0], PARADAS_SOLICITUD[1], { nombre: "Rechazada", adverso: true }],
      actual: 2,
    };
  }
  return resolver(PARADAS_SOLICITUD, { BORRADOR: 0, ENVIADA: 0, EN_VERIFICACION: 1, APROBADA: 2 }, estado);
}

/* ── Orden de mantenimiento ─────────────────────────────────────────────
   Abierta → En taller → Cerrada. "Esperando repuesto" es la parada de
   taller detenida (el vehículo sigue retenido); "Anulada" es el final
   adverso. */
const PARADAS_ORDEN: ParadaRiel[] = [{ nombre: "Abierta" }, { nombre: "En taller" }, { nombre: "Cerrada" }];

export function trayectoOrden(estado: string): Trayecto {
  if (estado === "ESPERANDO_REPUESTO") {
    return {
      paradas: [PARADAS_ORDEN[0], { nombre: "Esperando repuesto", adverso: true }, PARADAS_ORDEN[2]],
      actual: 1,
    };
  }
  if (estado === "ANULADA") {
    return {
      paradas: [PARADAS_ORDEN[0], PARADAS_ORDEN[1], { nombre: "Anulada", adverso: true }],
      actual: 2,
    };
  }
  return resolver(PARADAS_ORDEN, { ABIERTA: 0, EN_TALLER: 1, CERRADA: 2 }, estado);
}

/* ── Liquidación semanal ────────────────────────────────────────────────
   Emitida → Aprobada → Pagada. "Observada" es la emisión devuelta por el
   socio: sigue en la primera parada, en estado adverso. */
const PARADAS_LIQUIDACION: ParadaRiel[] = [
  { nombre: "Emitida" },
  { nombre: "Aprobada" },
  { nombre: "Pagada" },
];

export function trayectoLiquidacion(estado: string): Trayecto {
  if (estado === "OBSERVADA") {
    return {
      paradas: [{ nombre: "Observada", adverso: true }, PARADAS_LIQUIDACION[1], PARADAS_LIQUIDACION[2]],
      actual: 0,
    };
  }
  return resolver(PARADAS_LIQUIDACION, { EMITIDA: 0, APROBADA: 1, PAGADA: 2 }, estado);
}

/* ── Viaje ──────────────────────────────────────────────────────────────
   El trayecto más largo del sistema, y el único donde el riel coincide
   literalmente con un recorrido físico. "Programado" queda antes de la
   solicitud porque todavía no entró a la cola de despacho. */
const PARADAS_VIAJE: ParadaRiel[] = [
  { nombre: "Solicitado" },
  { nombre: "Asignado" },
  { nombre: "En camino" },
  { nombre: "En curso" },
  { nombre: "Finalizado" },
  { nombre: "Pagado" },
];

export function trayectoViaje(estado: string): Trayecto {
  if (estado === "CANCELADO") {
    return { paradas: [PARADAS_VIAJE[0], { nombre: "Cancelado", adverso: true }], actual: 1 };
  }
  if (estado === "SIN_CONDUCTOR") {
    return { paradas: [PARADAS_VIAJE[0], { nombre: "Sin conductor", adverso: true }], actual: 1 };
  }
  if (estado === "PROGRAMADO") {
    return { paradas: [{ nombre: "Programado" }, ...PARADAS_VIAJE], actual: 0 };
  }
  return resolver(
    PARADAS_VIAJE,
    { SOLICITADO: 0, OFERTADO: 0, ASIGNADO: 1, EN_CAMINO: 2, EN_CURSO: 3, FINALIZADO: 4, PAGADO: 5 },
    estado,
  );
}
