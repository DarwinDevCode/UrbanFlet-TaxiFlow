// CU-O06/CU-O07/CU-O08: mapa Leaflet + tiles OSM persistente en la pantalla
// "Mi turno" del conductor (arquitectura_software.md:109 exige Leaflet/MapLibre
// para el renderizado). Adaptado de apps/web-pasajero/src/RideMap.tsx — mismo
// patrón de íconos/control de ubicación a mano (ver comentario de
// ControlUbicacion más abajo), pero con marcadores propios del conductor:
// su propia posición, el punto de recogida del pasajero (oferta o viaje
// asignado) y el destino del viaje asignado, en vez de origen/destino/taxis
// anónimos del lado del pasajero.
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import markerIcon2x from "leaflet/dist/images/marker-icon-2x.png";
import markerIcon from "leaflet/dist/images/marker-icon.png";
import markerShadow from "leaflet/dist/images/marker-shadow.png";
import { useEffect } from "react";
import { MapContainer, Marker, Polyline, TileLayer, useMap } from "react-leaflet";

// Mismo fix estándar que RideMap.tsx: el icono por defecto de Leaflet se
// rompe con bundlers (rutas relativas resueltas contra el HTML, no contra el
// JS) — se apunta explícitamente a los assets importados por Vite.
delete (L.Icon.Default.prototype as unknown as { _getIconUrl?: unknown })._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});

// Marcador de la posición propia del conductor — mismo icono de taxi
// anónimo que ve el pasajero, pero aquí sí es "el mío" (sin ambigüedad
// posible: es el único de este tipo en este mapa).
// Tamaño triplicado (26px -> 78px): corregido tras hallazgo en pruebas
// reales — sin un font-size explícito el emoji heredaba el tamaño de fuente
// por defecto de Leaflet (mucho más chico que el iconSize), quedando casi
// invisible sobre el mapa.
const propiaIcon = L.divIcon({
  html: '<div style="font-size:66px;line-height:78px;text-align:center;filter:drop-shadow(0 0 2px rgba(0,0,0,.5))">🚕</div>',
  className: "conductor-propia-icon",
  iconSize: [78, 78],
  iconAnchor: [39, 39],
});

const recogidaIcon = new L.Icon({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIcon2x,
  shadowUrl: markerShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  className: "recogida-marker",
});

const destinoIcon = new L.Icon({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIcon2x,
  shadowUrl: markerShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  className: "destino-marker",
});

interface LatLon {
  lat: number;
  lon: number;
}

function Recentrar({ lat, lon }: LatLon) {
  const map = useMap();
  useEffect(() => {
    map.setView([lat, lon]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lat, lon]);
  return null;
}

// CU-O07 "Actualizar mi ubicación": control montado sobre el propio mapa,
// idéntico al de RideMap.tsx — construido a mano sobre `map.locate()` porque
// el plugin `leaflet.locatecontrol` no interopera de forma confiable con el
// bundle de Vite de este proyecto (ver comentario extenso en RideMap.tsx).
// No se reintroduce ese plugin acá tampoco.
const ControlUbicacion = L.Control.extend({
  options: { position: "topright" },
  onAdd(map: L.Map) {
    const boton = L.DomUtil.create("button", "leaflet-bar leaflet-control leaflet-control-locate");
    boton.type = "button";
    boton.title = "Ir a mi ubicación";
    boton.setAttribute("aria-label", "Ir a mi ubicación");
    Object.assign(boton.style, {
      width: "30px",
      height: "30px",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      cursor: "pointer",
    });
    boton.innerHTML =
      '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/></svg>';
    L.DomEvent.disableClickPropagation(boton);
    L.DomEvent.on(boton, "click", () => map.locate({ enableHighAccuracy: true, setView: false }));
    return boton;
  },
});

function ControlDeUbicacion({
  onEncontrada,
  onError,
}: {
  onEncontrada: (lat: number, lon: number) => void;
  onError: (mensaje: string) => void;
}) {
  const map = useMap();

  useEffect(() => {
    const control = new ControlUbicacion();
    control.addTo(map);

    const manejarEncontrada = (e: L.LocationEvent) => onEncontrada(e.latlng.lat, e.latlng.lng);
    const manejarError = (e: L.ErrorEvent) => {
      const mensaje =
        e.code === 1
          ? "Activa el permiso de ubicación en tu navegador para continuar: usualmente está en el ícono de candado/información junto a la barra de direcciones → Permisos del sitio → Ubicación."
          : "No se pudo obtener tu ubicación — verifica que el GPS esté activado e inténtalo de nuevo.";
      onError(mensaje);
    };

    map.on("locationfound", manejarEncontrada);
    map.on("locationerror", manejarError);

    return () => {
      map.off("locationfound", manejarEncontrada);
      map.off("locationerror", manejarError);
      control.remove();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map]);

  return null;
}

export interface DriverMapProps {
  propia: LatLon;
  recogida: LatLon | null;
  destino: LatLon | null;
  ruta: [number, number][] | null;
  onUbicacionEncontrada: (lat: number, lon: number) => void;
  onUbicacionError: (mensaje: string) => void;
}

// Mismo valor que RideMap.tsx (ALTO_MAPA) para consistencia visual entre las
// dos apps, aunque acá el mapa vive suelto en la pantalla en vez de dentro
// de un Card — ver PantallaTurno en App.tsx.
export const ALTO_MAPA = 480;

// El mapa se monta una sola vez por sesión de turno activa (ver App.tsx:
// PantallaTurno mantiene este componente montado mientras estado !==
// FUERA_DE_LINEA, independientemente de si hay oferta o viaje asignado) —
// nunca se debe recrear el <MapContainer> al llegar/aceptar/finalizar una
// oferta, solo cambian los overlays que se dibujan encima.
export function DriverMap({ propia, recogida, destino, ruta, onUbicacionEncontrada, onUbicacionError }: DriverMapProps) {
  return (
    <div style={{ height: ALTO_MAPA, borderRadius: "var(--radius-md)", overflow: "hidden" }}>
      <MapContainer center={[propia.lat, propia.lon]} zoom={15} style={{ height: "100%", width: "100%" }}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <Recentrar lat={propia.lat} lon={propia.lon} />
        <ControlDeUbicacion onEncontrada={onUbicacionEncontrada} onError={onUbicacionError} />
        <Marker position={[propia.lat, propia.lon]} icon={propiaIcon} interactive={false} />
        {recogida && <Marker position={[recogida.lat, recogida.lon]} icon={recogidaIcon} />}
        {destino && <Marker position={[destino.lat, destino.lon]} icon={destinoIcon} />}
        {ruta && ruta.length > 1 && <Polyline positions={ruta} pathOptions={{ color: "#1f6feb", weight: 4 }} />}
      </MapContainer>
    </div>
  );
}
