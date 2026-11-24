import type { PropsWithChildren } from "react";
import "./KpiCard.css";

type KpiTono = "exito" | "advertencia" | "serio" | "peligro";

const TONO_CLASE: Record<KpiTono, string> = {
  exito: "uf-instrumento--exito",
  advertencia: "uf-instrumento--advertencia",
  serio: "uf-instrumento--serio",
  peligro: "uf-instrumento--peligro",
};

/**
 * EL INSTRUMENTO — reemplaza a la tarjeta de métrica (Fase 1 del Sistema
 * Riel).
 *
 * La tarjeta anterior era el patrón más repetido de todo el sistema y el
 * más reconocible como genérico: caja blanca con borde, radio y sombra,
 * etiqueta en versalitas arriba y cifra grande abajo. Aparece igual en
 * cualquier producto de los últimos diez años.
 *
 * El instrumento quita la caja y apoya la cifra sobre una **escala con
 * marca de referencia**, como la lectura de un tablero de vehículo. La
 * ganancia no es solo visual: una cifra suelta ("78,3%") no dice si está
 * bien o mal, mientras que la misma cifra contra su marca de referencia se
 * interpreta sin explicación. Los instrumentos se agrupan en una franja
 * continua separada por líneas finas (`KpiRow`), no en cajas sueltas
 * flotando con espacio entre ellas.
 *
 * La API es exactamente la anterior -- los usos existentes no cambian. Los
 * dos props nuevos (`escala`, `referencia`) son opcionales: sin ellos el
 * instrumento se dibuja sin escala, que es lo correcto para un valor que
 * no tiene rango (una fecha, un nombre, un conteo sin techo conocido).
 */
export function KpiCard({
  etiqueta,
  valor,
  tono,
  descripcion,
  interpretacion,
  interpretacionTono,
  onClick,
  escala,
  referencia,
}: {
  etiqueta: string;
  valor: string;
  /** Color con significado de estado — omitir para un valor neutro. */
  tono?: KpiTono;
  /** Qué representa el indicador. Texto estático y breve. */
  descripcion?: string;
  /** Interpretación ya calculada y formateada por quien llama (ej.
   * "+15,2% vs. periodo anterior"). Nunca se deriva acá. */
  interpretacion?: string;
  interpretacionTono?: "exito" | "peligro";
  /** Convierte el instrumento en un control: quien llama abre el detalle
   * con los registros reales detrás del valor. */
  onClick?: () => void;
  /** Posición del valor dentro de su rango, 0 a 1. Dibuja la barra de la
   * escala. Omitir cuando el valor no tiene un rango con sentido. */
  escala?: number;
  /** Marca de referencia sobre la escala, 0 a 1 (el objetivo, el umbral,
   * el promedio). Es lo que permite leer la cifra sin explicación. */
  referencia?: number;
}) {
  const clases = [
    "uf-instrumento",
    tono ? TONO_CLASE[tono] : "",
    onClick ? "uf-instrumento--accionable" : "",
  ]
    .filter(Boolean)
    .join(" ");

  const pct = (n: number) => `${Math.max(0, Math.min(1, n)) * 100}%`;

  return (
    <div
      className={clases}
      role={onClick ? "button" : undefined}
      aria-label={onClick ? `${etiqueta}: ${valor}, ver detalle` : undefined}
      tabIndex={onClick ? 0 : undefined}
      onClick={onClick}
      onKeyDown={onClick ? (e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), onClick()) : undefined}
    >
      <p className="uf-rotulo uf-instrumento-etiqueta">{etiqueta}</p>
      <p className="uf-instrumento-valor">{valor}</p>

      {escala !== undefined && (
        <div className="uf-instrumento-escala">
          <i style={{ width: pct(escala) }} />
          {referencia !== undefined && <u style={{ left: pct(referencia) }} />}
        </div>
      )}

      {descripcion && <p className="uf-instrumento-descripcion">{descripcion}</p>}

      {interpretacion && (
        <p
          className={
            "uf-instrumento-interpretacion" +
            (interpretacionTono ? ` uf-instrumento-interpretacion--${interpretacionTono}` : "")
          }
        >
          {interpretacion}
        </p>
      )}

      {onClick && <p className="uf-instrumento-detalle">Ver detalle</p>}
    </div>
  );
}

/**
 * LA FRANJA DE INSTRUMENTOS — reemplaza la fila de tarjetas.
 *
 * Antes: `flex` con `gap`, es decir, cajas separadas por aire. Ahora: una
 * franja continua con una línea superior que la delimita y divisores
 * finos entre lecturas, como el tablero de un vehículo. Mismo nombre y
 * misma forma de uso, así que las pantallas no cambian.
 */
export function KpiRow({ children }: PropsWithChildren) {
  return <div className="uf-franja">{children}</div>;
}
