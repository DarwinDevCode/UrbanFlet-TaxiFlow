import { createContext, useContext } from "react";

/**
 * Navegación cruzada entre secciones de `web-interno` — hallazgo H4 de
 * `AUDITORIA_NIVEL_ESTRATEGICO.md` (Sección 6).
 *
 * Problema: `Seccion.render` es `() => JSX.Element`, sin ningún prop de
 * navegación, y `setSeccionActiva` vive solo en `Panel()` (`App.tsx`), pasado
 * al sidebar vía `AppShell.onNavigate`. Un botón "Ver detalle" dentro de un
 * panel (requisito de CU-E01, `nivel_estrategico.md` §4) no tenía forma de
 * cambiar la sección activa.
 *
 * Solución elegida — la de menor superficie de cambio: un contexto que
 * publica la MISMA función `setSeccionActiva` que ya usa el sidebar, más la
 * lista de secciones que el actor puede ver. Ninguna de las ~32 secciones
 * existentes cambia de firma; solo quien necesita navegar consume los hooks.
 *
 * La lista de disponibles es necesaria, no decorativa: `Panel()` resuelve la
 * sección activa dentro de `seccionesVisibles`, así que navegar a un id que
 * el rol no ve dejaría el área de contenido en blanco. Quien pinta un enlace
 * debe poder ocultarlo antes de ofrecerlo.
 *
 * Vive en `web-interno` y no en `shared-ui` a propósito: el modelo de
 * "secciones con id" es exclusivo de esta app (las PWAs de pasajero/conductor
 * no tienen sidebar ni secciones), así que subirlo al paquete compartido lo
 * acoplaría a un concepto que solo un consumidor entiende.
 *
 * Nota histórica: este contexto tuvo brevemente un `filtro` opcional en
 * `ir()` (más `filtroPendiente`/`consumirFiltroInicial`/`useFiltroInicial`)
 * para un piloto de drill-down por NAVEGACIÓN (KPI → cambia de sección con un
 * filtro ya aplicado). Ese piloto se descartó a favor de un modal en la
 * misma pantalla (`KpiDetalleModal`, ver `PanelCapacidades.tsx`/
 * `PanelDespacho.tsx`/`PanelRendimientoConductores.tsx`) — con eso, el
 * filtro de `ir()` quedó sin ningún consumidor real y se retiró para no
 * dejar 2 mecanismos de drill-down conviviendo. Si un caso futuro necesita
 * de verdad cambiar de sección CON un filtro pre-aplicado, reintroducirlo es
 * sencillo (ver el historial de este archivo), pero no antes de que exista
 * un consumidor real otra vez.
 */
export interface NavegacionSecciones {
  ir: (id: string) => void;
  disponibles: string[];
}

const NavegacionSeccionContext = createContext<NavegacionSecciones | null>(null);

export const NavegacionSeccionProvider = NavegacionSeccionContext.Provider;

/**
 * Devuelve una función `(id) => void` que activa la sección con ese `id`
 * (los mismos ids del array `SECCIONES` de `App.tsx`).
 *
 * Fuera del proveedor devuelve un no-op en vez de lanzar: así un panel puede
 * renderizarse aislado en un test sin montar todo `App`.
 */
export function useIrASeccion(): (id: string) => void {
  return useContext(NavegacionSeccionContext)?.ir ?? (() => {});
}

/** Ids de las secciones visibles para el actor actual (ya filtradas por rol). */
export function useSeccionesDisponibles(): string[] {
  return useContext(NavegacionSeccionContext)?.disponibles ?? [];
}
