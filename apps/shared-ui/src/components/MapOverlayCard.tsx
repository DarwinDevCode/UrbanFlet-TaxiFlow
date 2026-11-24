import type { ReactNode } from "react";
import "./MapOverlayCard.css";

export interface MapOverlayCardProps {
  /** Resumen de una línea, visible SIEMPRE (colapsado y expandido). Es lo
   * único que se ve en estado colapsado, así que debe alcanzar por sí solo
   * para saber en qué punto está el flujo. */
  resumen: ReactNode;
  /** Contenido completo — se pliega/despliega. */
  children: ReactNode;
  colapsado: boolean;
  onToggle: () => void;
  /** Cuando es false la tarjeta no se puede plegar y no muestra ni el resumen
   * ni el botón (p.ej. una oferta de viaje entrante, donde esconder el
   * contenido sería perder el viaje). */
  plegable?: boolean;
}

/**
 * Tarjeta flotante sobre el mapa persistente de `web-pasajero`/`web-conductor`
 * (ver §4 de CLAUDE.md: el ciclo de vida del viaje es un overlay sobre un
 * mismo mapa, nunca cambia de pantalla).
 *
 * Aporta dos cosas que antes cada app resolvía por su cuenta: el
 * posicionamiento/z-index (ahora desde la escala de capas de `tokens.css`, no
 * un número suelto por app) y el plegado a un resumen de una línea para
 * despejar el mapa sin perder de vista el estado del viaje.
 */
export function MapOverlayCard({ resumen, children, colapsado, onToggle, plegable = true }: MapOverlayCardProps) {
  const efectivamenteColapsado = plegable && colapsado;
  return (
    <div
      className="map-overlay-card"
      data-colapsado={efectivamenteColapsado ? "true" : "false"}
      data-plegable={plegable ? "true" : "false"}
    >
      {plegable && (
        <div className="map-overlay-resumen">
          <div className="map-overlay-resumen-contenido">{resumen}</div>
          <button
            type="button"
            className="map-overlay-toggle"
            onClick={onToggle}
            aria-expanded={!efectivamenteColapsado}
            aria-label={efectivamenteColapsado ? "Ampliar la tarjeta del viaje" : "Minimizar la tarjeta del viaje"}
            title={efectivamenteColapsado ? "Ampliar" : "Minimizar"}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
              <path d="M6 15l6-6 6 6" />
            </svg>
          </button>
        </div>
      )}
      <div className="map-overlay-cuerpo" aria-hidden={efectivamenteColapsado}>
        {children}
      </div>
    </div>
  );
}
