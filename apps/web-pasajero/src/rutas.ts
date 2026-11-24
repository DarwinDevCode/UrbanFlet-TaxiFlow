// CU-O04 P3: helpers de geocoding/ruta.
//
// `distanciaKm`/`estimarRuta` se movieron a `@urbanflet/shared-ui`
// (apps/shared-ui/src/api/rutas.ts) cuando web-conductor necesitó el mismo
// cálculo para su propio modo navegación (CU-O05/O06 paso 4, CU-O07 paso 4)
// — re-exportados acá tal cual para no tocar ningún import existente en este
// archivo. `geocodificarInverso` se queda local: es exclusivo de
// web-pasajero (geocoding directo desde el cliente, sí soporta CORS a
// diferencia de Directions — ver el comentario completo en
// shared-ui/src/api/rutas.ts).
import { getGoogleMapsApiKey } from "@urbanflet/shared-ui";

export { distanciaKm, estimarRuta } from "@urbanflet/shared-ui";
export type { RutaEstimada } from "@urbanflet/shared-ui";

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
