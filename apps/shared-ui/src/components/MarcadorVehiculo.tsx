import L from "leaflet";
import { Marker } from "react-leaflet";

/**
 * Ícono de posición de vehículo/conductor -- flecha de desplazamiento, no
 * el taxi genérico (🚕/🚖) que usaban antes `RideMap.tsx` (web-pasajero) y
 * `DriverMap.tsx` (web-conductor) cada uno por su cuenta.
 *
 * Orientación: la flecha rota según `heading` (0° = norte, sentido horario,
 * misma convención que `coords.heading` del navegador y el campo `rumbo`
 * que ya manda `POST /flota/posiciones`). Confirmado ANTES de construir
 * esto que ese dato no llega hoy a ningún lugar que lo consuma: la caché
 * de posición real (Redis `pos:{vehiculo_id}`, ver `flota/service.py::
 * reportar_posicion`) solo guarda `lat`/`lon`/`ts_servidor`/
 * `estado_servicio` -- `rumbo` se persiste en la colección `posiciones`
 * (traza cruda) pero ningún endpoint de lectura lo expone todavía. Por eso
 * `heading` es opcional y, sin dato, la flecha queda fija apuntando al
 * norte -- nunca se inventa una orientación.
 */
export interface IconoVehiculoOpciones {
  heading?: number | null;
  /** Vehículo propio o ya asignado -- se resalta en el color de acento, a
   * diferencia de un vehículo anónimo/de referencia. */
  destacado?: boolean;
  tamano?: number;
}

export function iconoVehiculo({ heading = null, destacado = false, tamano = 28 }: IconoVehiculoOpciones = {}): L.DivIcon {
  const rotacion = heading !== null && heading !== undefined ? `rotate(${heading}deg)` : "rotate(0deg)";
  const color = destacado ? "var(--color-accent)" : "var(--color-text-muted)";
  return L.divIcon({
    className: "uf-icono-vehiculo",
    html: `
      <div style="width:${tamano}px;height:${tamano}px;transform:${rotacion};filter:drop-shadow(0 1px 2px rgba(0,0,0,.45))">
        <svg width="${tamano}" height="${tamano}" viewBox="0 0 24 24">
          <path d="M12 2 L20 20 L12 15.5 L4 20 Z" fill="${color}" stroke="white" stroke-width="1.5" stroke-linejoin="round" />
        </svg>
      </div>
    `,
    iconSize: [tamano, tamano],
    iconAnchor: [tamano / 2, tamano / 2],
  });
}

export interface MarcadorVehiculoProps {
  lat: number;
  lon: number;
  heading?: number | null;
  destacado?: boolean;
  tamano?: number;
  interactive?: boolean;
}

/**
 * Componente único de marcador de vehículo/conductor -- reusado por los 3
 * portales (antes cada uno tenía su propio ícono hecho a mano). Envuelve
 * `iconoVehiculo()` sobre el `<Marker>` de `react-leaflet`.
 */
export function MarcadorVehiculo({
  lat,
  lon,
  heading = null,
  destacado = false,
  tamano,
  interactive = true,
}: MarcadorVehiculoProps) {
  return (
    <Marker
      position={[lat, lon]}
      icon={iconoVehiculo({ heading, destacado, tamano: tamano ?? (destacado ? 34 : 26) })}
      interactive={interactive}
    />
  );
}
