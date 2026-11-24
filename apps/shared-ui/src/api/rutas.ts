// Ruteo óptimo compartido entre web-pasajero y web-conductor (CU-O04 P3,
// CU-O05/O06 paso 4, CU-O07 paso 4 de operativo_operaciones_despacho.md).
// Vivía solo en apps/web-pasajero/src/rutas.ts hasta que web-conductor
// necesitó el mismo cálculo para su propio modo navegación — movido acá para
// que ningún portal reimplemente una segunda versión del mismo cliente.
//
// Directions API de Google no envía cabeceras CORS (confirmado con curl -I
// contra el endpoint real -- Geocoding sí las envía) — llamarla directo
// desde el navegador falla siempre, silenciosamente, y el cliente caía al
// respaldo de línea recta sin avisar que el dato real de Google nunca
// llegó. Por eso Directions se pide SIEMPRE al backend
// (GET /viajes/estimacion-ruta), que a su vez llama a Google server-side con
// la key (nunca expuesta al cliente para esto). Ese endpoint ya está
// diseñado para cualquier actor autenticado (pasajero y conductor), ver
// backend/src/viajes/router_trips.py.
import { apiFetch, getGoogleMapsApiKey } from "./client";

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

export interface LugarGeocodificado {
  lat: number;
  lon: number;
  direccion: string;
}

/**
 * Buscador de viajes (segunda pasada de ajustes de usabilidad, 2026):
 * geocoding hacia adelante (texto → coordenadas) para que pasajero y
 * conductor puedan localizar un lugar por nombre en vez de solo tocando el
 * mapa. Mismo cliente directo desde el navegador que ya usa
 * `geocodificarInverso` en web-pasajero (Geocoding API de Google sí trae
 * cabeceras CORS, a diferencia de Directions -- ver el comentario de arriba
 * de este archivo) -- se comparte acá porque ahora lo necesitan las dos apps,
 * mismo motivo por el que `estimarRuta`/`distanciaKm` ya viven en este
 * archivo. Sin autocompletado en vivo a propósito: este proyecto solo tiene
 * habilitada la API de Geocoding (arquitectura_software.md exige Google
 * exclusivamente para geocoding/rutas, nunca el SDK de Maps completo/Places)
 * -- geocodificar una dirección a medio escribir devuelve poco o nada útil,
 * así que la búsqueda es una acción explícita (Enter o el botón de buscar),
 * ver `BuscadorLugar`.
 *
 * `region=EC` sesga los resultados hacia Ecuador (sin restringir por completo
 * -- sigue siendo una dirección real de Google, no un filtro duro) porque
 * todo el dominio de este sistema es una cooperativa ecuatoriana. Devuelve
 * hasta 5 candidatos reales de Google (una dirección ambigua trae más de un
 * resultado en `results[]`, una específica trae uno solo) -- nunca una lista
 * fabricada. Sin key configurada, o sin texto, devuelve una lista vacía sin
 * intentar la llamada.
 */
export async function geocodificarLugar(texto: string): Promise<LugarGeocodificado[]> {
  const key = getGoogleMapsApiKey();
  const consulta = texto.trim();
  if (!key || !consulta) return [];
  try {
    const url = `https://maps.googleapis.com/maps/api/geocode/json?address=${encodeURIComponent(consulta)}&region=EC&key=${key}`;
    const resp = await fetch(url);
    const data = await resp.json();
    if (data.status !== "OK" || !Array.isArray(data.results)) return [];
    return (data.results as Array<{ formatted_address: string; geometry: { location: { lat: number; lng: number } } }>)
      .slice(0, 5)
      .map((r) => ({ lat: r.geometry.location.lat, lon: r.geometry.location.lng, direccion: r.formatted_address }));
  } catch {
    return [];
  }
}

// CU-O07 A6: umbral de desvío de ruta compartido — si la posición en vivo se
// aleja más de esto de la referencia usada para el último cálculo, hay que
// recalcular. Antes de este cambio no existía ninguna implementación real de
// A6 (backend/src/viajes/service_ejecucion.py lo documentaba como diferido
// "requiere un motor de ruteo que no existe en el stack" -- desactualizado,
// el motor ya existe vía estimarRuta/GET /viajes/estimacion-ruta desde
// CU-O04 P3). Este es el primer consumidor real del umbral.
export const UMBRAL_DESVIO_RUTA_KM = 2;
