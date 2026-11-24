import "leaflet/dist/leaflet.css";
import { MapContainer, TileLayer } from "react-leaflet";
import { MarcadorVehiculo } from "./MarcadorVehiculo";

export interface MapaPosicionProps {
  lat: number;
  lon: number;
  heading?: number | null;
  alto?: number;
  zoom?: number;
}

/**
 * Mapa de un solo punto, de solo lectura -- para mostrar la posición
 * conocida de UN vehículo (ej. el detalle de Flota en `web-interno`).
 * Distinto de `RideMap`/`DriverMap` (que manejan ruta, múltiples
 * marcadores, clics para elegir destino y el control de "mi ubicación") --
 * esos siguen viviendo en sus apps porque son mucho más que un mapa
 * estático. Este sí es genuinamente compartido: mismo Leaflet + mismas
 * tiles OSM que el resto del sistema, sin librería nueva.
 *
 * Nunca pide permiso de geolocalización ni escucha clics -- es una vista,
 * no un selector.
 */
export function MapaPosicion({ lat, lon, heading = null, alto = 260, zoom = 15 }: MapaPosicionProps) {
  return (
    <div style={{ height: alto, borderRadius: "var(--radius-md)", overflow: "hidden" }}>
      <MapContainer
        center={[lat, lon]}
        zoom={zoom}
        style={{ height: "100%", width: "100%" }}
        scrollWheelZoom={false}
        dragging={true}
        attributionControl={true}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <MarcadorVehiculo lat={lat} lon={lon} heading={heading} destacado interactive={false} />
      </MapContainer>
    </div>
  );
}
