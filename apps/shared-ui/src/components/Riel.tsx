import "./Riel.css";

/** Una parada del recorrido. El orden del array ES el orden del trayecto. */
export interface ParadaRiel {
  /** Nombre de la parada tal como lo lee una persona ("En taller", "Pagada").
   * Nunca el enum crudo del backend -- eso se traduce antes de llegar acá. */
  nombre: string;
  /** Marca una parada de salida no deseada (cancelado, rechazado, vencido).
   * Se pinta con el tono de peligro en vez del ámbar del recorrido. */
  adverso?: boolean;
}

export interface RielProps {
  paradas: ParadaRiel[];
  /** Índice de la parada donde está el objeto ahora. Todo lo anterior se
   * pinta como recorrido; todo lo posterior, como pendiente. */
  actual: number;
  /** `completo`: la franja de un plano o el encabezado de un detalle, con
   * los nombres de la primera, la actual y la última parada debajo.
   * `mini`: dentro de una fila de registro -- solo la línea, sin nombres.
   * `etiquetado`: como mini pero con el nombre de la parada actual debajo. */
  variante?: "completo" | "mini" | "etiquetado";
}

/**
 * EL RIEL — componente firma del Sistema Riel (Fase 1 del rediseño de
 * identidad, ver SISTEMA_RIEL.md).
 *
 * Sustituye a la píldora de estado en todo el sistema. El punto de partida
 * es un hecho del dominio que casi ningún otro sistema comparte: en
 * UrbanFleet **todo objeto del negocio es un trayecto entre paradas
 * conocidas** -- un viaje va de solicitado a pagado, una solicitud de socio
 * de enviada a aprobada, una orden de taller de abierta a cerrada, una
 * liquidación de emitida a pagada, un documento de vigente a vencido.
 *
 * Una píldora de color dice EN QUÉ estado está. El riel dice eso y además
 * CUÁNTO FALTA, en el mismo espacio -- así que además de ser la firma
 * visual del sistema, es estrictamente más informativo que lo que
 * reemplaza.
 *
 * Accesibilidad: el riel es decorativo para un lector de pantalla (la
 * información va en el texto de la parada actual, que siempre se anuncia).
 * En la variante `mini`, donde no hay texto visible, el estado viaja en el
 * `aria-label` del contenedor -- nunca queda un estado que solo exista como
 * color.
 */
export function Riel({ paradas, actual, variante = "completo" }: RielProps) {
  if (paradas.length === 0) return null;

  const indice = Math.max(0, Math.min(actual, paradas.length - 1));
  const paradaActual = paradas[indice];
  const esAdverso = Boolean(paradaActual.adverso);

  const piezas: React.ReactNode[] = [];
  paradas.forEach((parada, i) => {
    const recorrido = i < indice;
    const esActual = i === indice;

    if (i > 0) {
      piezas.push(
        <span
          key={`tramo-${i}`}
          className={`uf-riel-tramo${recorrido || esActual ? "" : " uf-riel-tramo--pendiente"}`}
          data-adverso={esActual && esAdverso ? "" : undefined}
        />,
      );
    }
    piezas.push(
      <span
        key={`nodo-${i}-${parada.nombre}`}
        className={
          "uf-riel-nodo" +
          (esActual ? " uf-riel-nodo--actual" : recorrido ? "" : " uf-riel-nodo--pendiente")
        }
        data-adverso={esActual && esAdverso ? "" : undefined}
      />,
    );
  });

  const linea = (
    <span
      className={`uf-riel${variante === "mini" || variante === "etiquetado" ? " uf-riel--mini" : ""}`}
      // El riel en sí no aporta nada a un lector de pantalla: el estado ya
      // viaja como texto (en el pie, o en el aria-label de más abajo).
      aria-hidden="true"
    >
      {piezas}
    </span>
  );

  if (variante === "mini") {
    return (
      <span className="uf-riel-bloque" role="img" aria-label={`Estado: ${paradaActual.nombre}`}>
        {linea}
      </span>
    );
  }

  if (variante === "etiquetado") {
    return (
      <span className="uf-riel-bloque">
        {linea}
        <span className={`uf-riel-actual-nombre${esAdverso ? " uf-riel-actual-nombre--adverso" : ""}`}>
          {paradaActual.nombre}
        </span>
      </span>
    );
  }

  const primera = paradas[0];
  const ultima = paradas[paradas.length - 1];
  const mostrarExtremos = indice > 0 && indice < paradas.length - 1;

  return (
    <span className="uf-riel-bloque">
      {linea}
      <span className="uf-riel-pie">
        {mostrarExtremos && <span className="uf-riel-extremo">{primera.nombre}</span>}
        <span className={`uf-riel-actual-nombre${esAdverso ? " uf-riel-actual-nombre--adverso" : ""}`}>
          {paradaActual.nombre}
        </span>
        {mostrarExtremos && <span className="uf-riel-extremo">{ultima.nombre}</span>}
      </span>
    </span>
  );
}
