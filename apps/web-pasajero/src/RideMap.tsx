// CU-O04 P1/P3: mapa Leaflet + tiles OSM (arquitectura_software.md:109 exige
// Leaflet/MapLibre para el renderizado, no el SDK de Google Maps). Google
// solo se usa para geocoding/direcciones (fetch directo a su API HTTP con la
// key ya provisionada por configureGoogleMapsApiKey) — nunca para pintar el
// mapa en sí.
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import markerIcon2x from "leaflet/dist/images/marker-icon-2x.png";
import markerIcon from "leaflet/dist/images/marker-icon.png";
import markerShadow from "leaflet/dist/images/marker-shadow.png";
import { useEffect } from "react";
import { MapContainer, Marker, Polyline, TileLayer, useMap, useMapEvents } from "react-leaflet";

// El icono por defecto de Leaflet se rompe con bundlers (rutas relativas
// resueltas contra el HTML, no contra el JS) — fix estándar documentado por
// el propio proyecto Leaflet: apuntar explícitamente a los assets importados.
delete (L.Icon.Default.prototype as unknown as { _getIconUrl?: unknown })._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});

const destinoIcon = new L.Icon({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIcon2x,
  shadowUrl: markerShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  className: "destino-marker",
});

// CU-O04 P1: "íconos anónimos" de taxis cercanos — sin popup, sin datos de
// conductor/vehículo, solo un marcador genérico.
const taxiIcon = L.divIcon({
  html: "🚕",
  className: "taxi-icon-anonimo",
  iconSize: [22, 22],
  iconAnchor: [11, 11],
});

// A diferencia de `taxiIcon` (anónimo, para el radio de búsqueda antes de
// asignar), este ícono representa al conductor YA asignado a este viaje —
// deliberadamente distinto (más grande, resaltado) para que el pasajero no
// lo confunda con los taxis anónimos cercanos.
const conductorIcon = L.divIcon({
  html: '<div style="font-size:22px;filter:drop-shadow(0 0 2px rgba(0,0,0,.5))">🚖</div>',
  className: "conductor-icon-asignado",
  iconSize: [30, 30],
  iconAnchor: [15, 15],
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

function ClicksDelMapa({ onClick }: { onClick: (lat: number, lon: number) => void }) {
  useMapEvents({
    click(e) {
      onClick(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

// CU-O04 A2/"Actualizar mi ubicación": en vez de un botón aparte debajo del
// mapa, un control montado sobre el propio mapa — mismo lugar/comportamiento
// que el botón "mi ubicación" de Google Maps, pero construido a mano sobre
// `map.locate()` (nativo de Leaflet, sin plugin externo): el plugin de la
// comunidad `leaflet.locatecontrol` no logra engancharse de forma confiable
// al bundle de Vite (su patrón UMD deja `L.control.locate` indefinido contra
// la instancia de `L` que importa este archivo), así que se evita esa
// dependencia frágil por completo. Un solo control cubre tanto el centrado
// inicial como el reintento tras un permiso denegado.
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

export interface RideMapProps {
  origen: LatLon;
  destino: LatLon | null;
  ruta: [number, number][] | null;
  cercanos: LatLon[];
  // Posición conocida del conductor ya asignado a este viaje (distinta de
  // `cercanos`, que son anónimos) — null mientras no se conoce/no aplica.
  conductor?: LatLon | null;
  onMapaClick: (lat: number, lon: number) => void;
  onUbicacionEncontrada: (lat: number, lon: number) => void;
  onUbicacionError: (mensaje: string) => void;
  // El mapa persiste montado durante todo el viaje (ver App.tsx); una vez
  // que hay un destino fijado por el propio viaje ya no tiene sentido seguir
  // aceptando clics para "elegir destino" — por defecto sigue habilitado
  // (comportamiento previo) y el padre lo desactiva explícitamente.
  clicksHabilitados?: boolean;
  // Sección 1.2 de ux_complementaria.md (vista pública de "Compartir viaje"):
  // sin sesión, sin clics de "elegir destino", sin botón de "mi ubicación"
  // (no tiene sentido pedirle geolocalización a un contacto que solo mira).
  soloLectura?: boolean;
  // Cuando es true, el mapa llena el 100% de la altura de su contenedor en
  // vez de la altura fija ALTO_MAPA -- usado en la vista de viaje activo
  // (VistaViaje), que ahora ocupa todo el alto disponible de la pantalla en
  // vez de un recuadro fijo. El resto de usos (historial, vista pública
  // compartida) siguen con altura fija.
  llenarAltura?: boolean;
}

export const ALTO_MAPA = 480;

export function RideMap({
  origen,
  destino,
  ruta,
  cercanos,
  conductor = null,
  onMapaClick,
  onUbicacionEncontrada,
  onUbicacionError,
  clicksHabilitados = true,
  soloLectura = false,
  llenarAltura = false,
}: RideMapProps) {
  return (
    <div style={{ height: llenarAltura ? "100%" : ALTO_MAPA, borderRadius: "var(--radius-md)", overflow: "hidden" }}>
      <MapContainer center={[origen.lat, origen.lon]} zoom={15} style={{ height: "100%", width: "100%" }}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <Recentrar lat={origen.lat} lon={origen.lon} />
        {!soloLectura && clicksHabilitados && <ClicksDelMapa onClick={onMapaClick} />}
        {!soloLectura && (
          <ControlDeUbicacion onEncontrada={onUbicacionEncontrada} onError={onUbicacionError} />
        )}
        <Marker position={[origen.lat, origen.lon]} />
        {destino && <Marker position={[destino.lat, destino.lon]} icon={destinoIcon} />}
        {ruta && ruta.length > 1 && <Polyline positions={ruta} pathOptions={{ color: "#1f6feb", weight: 4 }} />}
        {cercanos.map((c, i) => (
          <Marker key={i} position={[c.lat, c.lon]} icon={taxiIcon} interactive={false} />
        ))}
        {conductor && <Marker position={[conductor.lat, conductor.lon]} icon={conductorIcon} />}
      </MapContainer>
    </div>
  );
}
