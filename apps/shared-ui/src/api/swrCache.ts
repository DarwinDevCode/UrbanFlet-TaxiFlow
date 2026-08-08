import { useCallback, useEffect, useRef, useState } from "react";

/** Caché stale-while-revalidate casera, sin librería nueva -- mismo criterio
 * ya usado en este proyecto para `theme.ts`/`densidad.ts` (mecanismo a mano
 * en vez de sumar una dependencia, dado el alcance del proyecto). Vive en
 * memoria del tab (un `Map` a nivel de módulo, no `localStorage`): sobrevive
 * a navegar entre secciones de `web-interno` -- donde `Panel()` desmonta y
 * vuelve a montar el componente de cada sección -- pero se pierde al
 * recargar la página, que es la intención (evitar refetch entre
 * navegaciones dentro de la misma sesión, no persistir datos de negocio).
 *
 * Deliberadamente NO usado en pantallas con su propio polling (`Flota`,
 * `PanelFlota`, `PanelDespacho`, `Monitoreo`) -- esas ya se refrescan solas
 * cada pocos segundos y no necesitan (ni deben) mostrar un dato "viejo" de
 * caché al montar. */

interface CacheEntry<T> {
  data: T;
  ts: number;
}

const cache = new Map<string, CacheEntry<unknown>>();
const inflight = new Map<string, Promise<unknown>>();

/** Invalida una key exacta -- la próxima vez que se pida, se refetchea. */
export function invalidateSwr(key: string): void {
  cache.delete(key);
}

/** Invalida todas las keys cuyo path (antes del `?`) empiece con `prefix`.
 * Uso típico: tras una mutación (aprobar/rechazar/crear/editar), invalidar
 * el recurso completo sin importar qué combinación de filtros tenía cada
 * key cacheada -- la próxima vez que se visite cualquiera de esas
 * combinaciones, se refetchea en vez de mostrar el dato pre-mutación. */
export function invalidateSwrPrefix(prefix: string): void {
  for (const key of cache.keys()) {
    if (key.startsWith(prefix)) cache.delete(key);
  }
}

export interface UseSwrResult<T> {
  data: T | undefined;
  /** true solo mientras no hay ningún dato que mostrar todavía (primera
   * carga sin caché) -- una revalidación en segundo plano con caché
   * disponible NO pone esto en true, para no parpadear la pantalla. */
  loading: boolean;
  /** true durante cualquier fetch en curso, incluida la revalidación en
   * segundo plano -- para un indicador discreto opcional, no bloqueante. */
  revalidando: boolean;
  error: unknown;
  refetch: () => Promise<void>;
}

/** Hook stale-while-revalidate: si `key` ya tiene datos en caché, los
 * devuelve de inmediato (sin pausa visible) y dispara un refetch en segundo
 * plano que actualiza la vista sola si el servidor devolvió algo distinto.
 * Si no hay caché, `loading` es true hasta que llega la primera respuesta.
 * `key === null` desactiva el hook (útil para fetches condicionales sin
 * romper las reglas de hooks). */
export function useSwr<T>(key: string | null, fetcher: () => Promise<T>): UseSwrResult<T> {
  const cachedInicial = key ? (cache.get(key) as CacheEntry<T> | undefined) : undefined;
  const [data, setData] = useState<T | undefined>(cachedInicial?.data);
  const [loading, setLoading] = useState(!cachedInicial);
  const [revalidando, setRevalidando] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const ejecutar = useCallback(async () => {
    if (!key) return;
    setRevalidando(true);
    try {
      let promesa = inflight.get(key) as Promise<T> | undefined;
      if (!promesa) {
        promesa = fetcherRef.current().finally(() => inflight.delete(key));
        inflight.set(key, promesa);
      }
      const resultado = await promesa;
      cache.set(key, { data: resultado, ts: Date.now() });
      setData(resultado);
      setError(null);
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
      setRevalidando(false);
    }
  }, [key]);

  useEffect(() => {
    if (!key) return;
    const cachedAhora = cache.get(key) as CacheEntry<T> | undefined;
    if (cachedAhora) {
      setData(cachedAhora.data);
      setLoading(false);
    } else {
      setData(undefined);
      setLoading(true);
    }
    ejecutar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return { data, loading, revalidando, error, refetch: ejecutar };
}
