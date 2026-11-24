const TAMANO_TEXTO_KEY = "urbanflet.tamanoTexto";

export type TamanoTexto = "normal" | "grande" | "muy_grande";

/** Factor sobre los 6 escalones de `--font-size-*` (ver tokens.css). No se
 * redefine cada escalón por separado a propósito: un solo factor conserva la
 * proporción original del sistema de diseño, así que "grande" es la misma
 * jerarquía tipográfica, más grande — no una escala distinta. */
const FACTOR: Record<TamanoTexto, string> = {
  normal: "1",
  grande: "1.15",
  muy_grande: "1.3",
};

function aplicarAtributo(tamano: TamanoTexto): void {
  document.documentElement.style.setProperty("--font-scale", FACTOR[tamano]);
}

/** Llamar de forma sincrónica en `main.tsx`, antes del primer render — mismo
 * mecanismo que `theme.ts`/`densidad.ts`: aplica el último valor conocido
 * (cache local) sin esperar `GET /preferencias`, para que el texto no
 * "salte" de tamaño al cargar. */
export function aplicarTamanoTextoInicial(): void {
  const guardado = localStorage.getItem(TAMANO_TEXTO_KEY);
  if (guardado === "normal" || guardado === "grande" || guardado === "muy_grande") {
    aplicarAtributo(guardado);
  }
}

/** Aplica el tamaño real (server-truth, vía `GET /preferencias`) y lo cachea
 * localmente para la próxima carga (`aplicarTamanoTextoInicial`). */
export function aplicarTamanoTexto(tamano: TamanoTexto): void {
  aplicarAtributo(tamano);
  localStorage.setItem(TAMANO_TEXTO_KEY, tamano);
}
