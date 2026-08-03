// Decodifica el payload del JWT solo para mostrar datos en la UI (nombre de
// usuario, etc.) — NUNCA se usa para decidir permisos en el cliente; el
// backend resuelve el rol por petición (ver core/rbac.py) y es la única
// fuente de verdad de autorización.
export function decodeJwtPayload<T = Record<string, unknown>>(token: string): T | null {
  try {
    const [, payload] = token.split(".");
    const json = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(json) as T;
  } catch {
    return null;
  }
}
