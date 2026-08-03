// CU-O04 P3: helpers de geocoding/ruta.
//
// Corregido tras hallazgo en pruebas reales: Directions API de Google NO
// envía cabeceras CORS (confirmado con curl -I contra el endpoint real —
// Geocoding sí las envía, `Access-Control-Allow-Origin: *`). Llamar a
// Directions directo desde el navegador siempre fallaba, silenciosamente, y
// la app caía al respaldo de línea recta sin avisar que el dato real de
// Google nunca llegó — la tarifa mostrada al pasajero podía estar basada en
// una estimación mucho más cruda de lo que parecía. Directions ahora se pide
// SIEMPRE al propio backend (GET /viajes/estimacion-ruta), que a su vez
// llama a Google server-side con la key (nunca expuesta para esto). Geocoding
// (geocodificarInverso, abajo) sigue siendo directo desde el cliente porque
// sí soporta CORS — no tiene el mismo problema.
import { apiFetch, getGoogleMapsApiKey } from "@urbanflet/shared-ui";

export function distanciaKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const radioTierraKm = 6371;
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return radioTierraKm * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

export interface RutaEstimada {
  ruta: [number, number][];
  distanciaKm: number;
  duracionMin: number;
  origenDirections: boolean;
}

interface EstimacionRutaResponse {
  ruta: [number, number][];
  distancia_km: number;
  duracion_min: number;
  origen_directions: boolean;
}

export async function estimarRuta(
  origen: { lat: number; lon: number },
  destino: { lat: number; lon: number },
): Promise<RutaEstimada> {
  try {
    const resp = await apiFetch<EstimacionRutaResponse>(
      `/viajes/estimacion-ruta?origen_lat=${origen.lat}&origen_lon=${origen.lon}` +
        `&destino_lat=${destino.lat}&destino_lon=${destino.lon}`,
    );
    return {
      ruta: resp.ruta,
      distanciaKm: resp.distancia_km,
      duracionMin: resp.duracion_min,
      origenDirections: resp.origen_directions,
    };
  } catch {
    // Si ni siquiera se pudo llegar al backend (red caída) — respaldo de
    // línea recta calculado en el cliente, última instancia. El respaldo
    // "normal" (Directions falló pero el backend respondió) ya viene
    // resuelto en el cuerpo de la respuesta de arriba (origen_directions).
    const km = distanciaKm(origen.lat, origen.lon, destino.lat, destino.lon);
    return {
      ruta: [
        [origen.lat, origen.lon],
        [destino.lat, destino.lon],
      ],
      distanciaKm: km,
      duracionMin: (km / 25) * 60,
      origenDirections: false,
    };
  }
}

export async function geocodificarInverso(lat: number, lon: number): Promise<string | null> {
  const key = getGoogleMapsApiKey();
  if (!key) return null;
  try {
    const url = `https://maps.googleapis.com/maps/api/geocode/json?latlng=${lat},${lon}&key=${key}`;
    const resp = await fetch(url);
    const data = await resp.json();
    if (data.status === "OK" && data.results?.[0]) {
      return data.results[0].formatted_address as string;
    }
  } catch {
    // Geocoding inverso es solo un dato de contexto (nice-to-have) — el
    // valor que realmente se envía al backend sigue siendo lat/lon.
  }
  return null;
}
