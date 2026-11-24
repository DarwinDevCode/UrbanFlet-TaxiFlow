import { tokenStorage } from "./tokenStorage";

export class ApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly status: number,
    // Presente solo en 422 de validación (ver backend/src/core/validation.py)
    // -- permite mostrar el mensaje junto al campo exacto que falló, en vez
    // de un banner genérico. Vacío para el resto de errores (403/404/409/...).
    public readonly fieldErrors: Record<string, string> = {},
  ) {
    super(message);
  }
}

interface ErrorCampo {
  campo: string;
  mensaje: string;
}

/** Mensaje de un campo específico dentro de un ApiError de validación, o
 * `undefined` si el error no aplica a ese campo (u otro tipo de error). Uso
 * típico: `error={fieldError(error, "umbral_intentos_fallidos")}` pasado
 * directo al prop `error` de `TextField`. */
export function fieldError(error: unknown, campo: string): string | undefined {
  if (!(error instanceof ApiError)) return undefined;
  return error.fieldErrors[campo];
}

interface TokenPair {
  access_token: string;
  refresh_token: string;
}

let baseUrl = "";

export function configureApiClient(url: string) {
  baseUrl = url;
}

export function getApiBaseUrl(): string {
  return baseUrl;
}

// La API key de Google Maps (Maps JavaScript API, Geocoding, Directions) es
// específica de cada app (restringida por sitio web en Google Cloud), así
// que cada app la lee de su propio import.meta.env.VITE_GOOGLE_MAPS_API_KEY
// y la registra aquí una vez al arrancar — este paquete compartido nunca la
// lee directamente ni la codifica como literal, igual que baseUrl arriba.
let googleMapsApiKey = "";

export function configureGoogleMapsApiKey(key: string) {
  googleMapsApiKey = key;
}

export function getGoogleMapsApiKey(): string {
  return googleMapsApiKey;
}

async function parseError(response: Response): Promise<never> {
  const body = await response.json().catch(() => ({ code: "UNKNOWN", message: response.statusText }));
  const fieldErrors: Record<string, string> = {};
  if (Array.isArray(body.errores)) {
    for (const e of body.errores as ErrorCampo[]) {
      if (e && typeof e.campo === "string" && typeof e.mensaje === "string") fieldErrors[e.campo] = e.mensaje;
    }
  }
  throw new ApiError(body.code ?? "UNKNOWN", body.message ?? response.statusText, response.status, fieldErrors);
}

async function refreshTokens(): Promise<boolean> {
  const refreshToken = tokenStorage.getRefresh();
  if (!refreshToken) return false;

  let response: Response;
  try {
    response = await fetch(`${baseUrl}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  } catch {
    // Fallo de red (backend caído, wifi cortado): NO se borran los tokens.
    // El refresh token puede seguir siendo perfectamente válido; cerrarle la
    // sesión al usuario por un corte transitorio sería peor que dejar que la
    // petición falle y se reintente después.
    return false;
  }

  if (!response.ok) {
    tokenStorage.clear();
    return false;
  }
  const tokens: TokenPair = await response.json();
  tokenStorage.set(tokens.access_token, tokens.refresh_token);
  return true;
}

// Single-flight: una sola renovación en vuelo a la vez, compartida por todas
// las peticiones que hayan chocado con el mismo 401.
//
// Sin esto, cada expiración del access token producía una estampida: TODAS
// las peticiones en vuelo en ese instante (el polling de NotificacionesBell
// cada 20s, la revalidación SWR de la sección abierta, etc.) recibían 401 a
// la vez y cada una llamaba `POST /auth/refresh` por su cuenta con el MISMO
// refresh token. El backend no invalida el refresh token al usarlo, así que
// las N llamadas devuelven 200 — pero cada una emite un par de tokens nuevo
// y registra una SESIÓN nueva (`core/sessions.py::registrar_sesion`), de ahí
// las sesiones fantasma que aparecían en "Mis sesiones"/Módulo 1.4. Además,
// las N escrituras a `tokenStorage` se pisan entre sí (access y refresh se
// guardan en dos `setItem` separados, así que un entrelazado desafortunado
// deja un par mezclado), y `_registrar_fallo_refresh` suspende la cuenta
// entera a los 3 fallos de refresh — una estampida de 3 alcanza ese umbral
// de un solo golpe en vez de a lo largo de 3 incidentes distintos.
let renovacionEnVuelo: Promise<boolean> | null = null;

function renovarUnaSolaVez(): Promise<boolean> {
  if (!renovacionEnVuelo) {
    renovacionEnVuelo = refreshTokens().finally(() => {
      renovacionEnVuelo = null;
    });
  }
  return renovacionEnVuelo;
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  auth?: boolean;
  idempotencyKey?: string;
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, auth = true, idempotencyKey } = options;

  const doRequest = async (): Promise<Response> => {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (auth) {
      const token = tokenStorage.getAccess();
      if (token) headers.Authorization = `Bearer ${token}`;
    }
    if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;

    return fetch(`${baseUrl}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  };

  // Token con el que sale ESTA petición: si al volver con 401 resulta que ya
  // no es el vigente, es que otra petición renovó mientras esta viajaba —
  // basta reintentar con el nuevo, sin gastar una renovación de más.
  const tokenEnviado = auth ? tokenStorage.getAccess() : null;
  let response = await doRequest();

  if (response.status === 401 && auth) {
    const yaRenovadoPorOtra = tokenStorage.getAccess() !== tokenEnviado;
    const renovado = yaRenovadoPorOtra || (await renovarUnaSolaVez());
    if (renovado) {
      response = await doRequest();
    }
  }

  if (!response.ok) {
    await parseError(response);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

// Ronda 2 del flujo de fallas, Fase A/C: primer mecanismo de carga de
// archivos del proyecto -- multipart/form-data, así que no puede pasar por
// `apiFetch` (que siempre serializa `body` como JSON). Reusa el mismo
// single-flight de renovación de token que `apiFetch` en vez de duplicar su
// propia lógica de reintento.
export interface ArchivoSubidoOut {
  id: string;
  nombre_original: string;
  content_type: string;
  tamano_bytes: number;
  contexto: string;
  propietario_id: string;
  ts_creacion: string;
}

export async function subirArchivo(file: File, contexto: string): Promise<ArchivoSubidoOut> {
  const doRequest = async (): Promise<Response> => {
    const formData = new FormData();
    formData.append("contexto", contexto);
    formData.append("file", file);
    const headers: Record<string, string> = {};
    const token = tokenStorage.getAccess();
    if (token) headers.Authorization = `Bearer ${token}`;
    return fetch(`${baseUrl}/archivos`, { method: "POST", headers, body: formData });
  };

  const tokenEnviado = tokenStorage.getAccess();
  let response = await doRequest();
  if (response.status === 401) {
    const yaRenovadoPorOtra = tokenStorage.getAccess() !== tokenEnviado;
    const renovado = yaRenovadoPorOtra || (await renovarUnaSolaVez());
    if (renovado) response = await doRequest();
  }
  if (!response.ok) await parseError(response);
  return (await response.json()) as ArchivoSubidoOut;
}

/** URL autenticada de un archivo -- no sirve como `<img src>` directo (el
 * navegador no adjunta el Bearer token a una carga de imagen plana); usar
 * `obtenerArchivoBlobUrl` para renderizarlo. */
export function urlArchivo(archivoId: string): string {
  return `${baseUrl}/archivos/${archivoId}`;
}

/** Descarga un archivo protegido y devuelve un Object URL listo para
 * `<img src>` -- quien lo use debe revocarlo (`URL.revokeObjectURL`) cuando
 * ya no lo necesite. */
export async function obtenerArchivoBlobUrl(archivoId: string): Promise<string> {
  const headers: Record<string, string> = {};
  const token = tokenStorage.getAccess();
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${baseUrl}/archivos/${archivoId}`, { headers });
  if (!response.ok) await parseError(response);
  const blob = await response.blob();
  return URL.createObjectURL(blob);
}
