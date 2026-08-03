import { tokenStorage } from "./tokenStorage";

export class ApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly status: number,
  ) {
    super(message);
  }
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
  throw new ApiError(body.code ?? "UNKNOWN", body.message ?? response.statusText, response.status);
}

async function refreshTokens(): Promise<boolean> {
  const refreshToken = tokenStorage.getRefresh();
  if (!refreshToken) return false;

  const response = await fetch(`${baseUrl}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!response.ok) {
    tokenStorage.clear();
    return false;
  }
  const tokens: TokenPair = await response.json();
  tokenStorage.set(tokens.access_token, tokens.refresh_token);
  return true;
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

  let response = await doRequest();

  if (response.status === 401 && auth) {
    const refreshed = await refreshTokens();
    if (refreshed) {
      response = await doRequest();
    }
  }

  if (!response.ok) {
    await parseError(response);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
