import "./Badge.css";

type BadgeTono = "neutral" | "exito" | "advertencia" | "peligro";

/**
 * LA MARCA — reemplaza a la píldora de estado (Fase 1 del Sistema Riel).
 *
 * En el sistema nuevo, el estado de cualquier objeto que recorra un
 * trayecto se muestra con `Riel`, no acá. Este componente queda para lo
 * que de verdad es una **categoría** y no una etapa: el tipo de una orden
 * (preventiva/correctiva), el método de un pago, el rol de un actor.
 *
 * La forma cambia de píldora (`border-radius: 999px`, el chip que usa
 * cualquier interfaz) a marca angular: un bloque recto con una barra de
 * color a la izquierda, como la marca de un plano. Conserva la API
 * anterior, así que las pantallas que aún la usan para estado siguen
 * funcionando mientras se migran al riel.
 */
export function Badge({ texto, tono = "neutral" }: { texto: string; tono?: BadgeTono }) {
  return <span className={`uf-marca uf-marca--${tono}`}>{texto}</span>;
}
