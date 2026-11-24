import { useEffect, useRef, useState, type ReactNode } from "react";
import "./DataTable.css";

/** Prioridad de la columna al competir por el ancho disponible.
 *
 * Los umbrales se miden sobre el CONTENEDOR de la tabla, no sobre el viewport
 * (`@container` en DataTable.css) — una tabla en la columna angosta de un
 * dashboard tiene que comportarse como una tabla angosta aunque la pantalla
 * sea de escritorio.
 *
 * - `alta` (default): siempre visible.
 * - `media`: se oculta con el contenedor por debajo de 700px.
 * - `baja`: se oculta con el contenedor por debajo de 900px.
 *
 * Es OPT-IN a propósito: una tabla que no marque nada se comporta igual que
 * antes (todas las columnas visibles + scroll horizontal). Solo se marca como
 * `media`/`baja` una columna cuyo dato ya esté disponible en otro lado (el
 * detalle de la fila, típicamente) — nunca el único lugar donde se puede leer
 * un valor. */
export type PrioridadColumna = "alta" | "media" | "baja";

export interface Column<T> {
  header: string;
  render: (row: T) => ReactNode;
  /** Ancho CSS fijo (ej. "140px"). El contenido hace WRAP dentro de ese ancho
   * en vez de truncarse — usar cuando el valor completo tiene que verse sí o
   * sí en la tabla. Sin `width`, la celda trunca con "…" y el valor completo
   * se consulta con la previsualización (ver `DataTable`). */
  width?: string;
  prioridad?: PrioridadColumna;
  /** Desactiva el truncado en esa columna (contenido que no es texto y no
   * debe recortarse nunca: un botón de acción, un grupo de badges). */
  sinTruncar?: boolean;
  /** Columna de cifras: se alinea a la derecha y usa `tabular-nums`, para
   * que las unidades caigan en la misma vertical y las magnitudes se
   * puedan comparar de un vistazo (Sistema Riel, Fase 1). */
  numerica?: boolean;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  keyField: (row: T) => string;
  vacio?: string;
  /** Alto máximo con scroll interno -- para listas largas (ej. bitácora de
   * auditoría con 100 filas) que si no, estiran la página entera y dejan
   * el bloque vecino (gráfico) visualmente insignificante en comparación. */
  altoMaximo?: number;
  /** Oculta el contador de resultados al pie de la tabla. Por defecto se
   * muestra siempre ("N resultados") -- usar `true` solo cuando la pantalla
   * ya indica el total por otro lado (típicamente `Pagination`, que ya
   * muestra "X–Y de Z"), para no mostrar dos contadores con criterios
   * distintos uno debajo del otro. */
  ocultarContador?: boolean;
}

interface Previsualizacion {
  texto: string;
  x: number;
  y: number;
}

/**
 * Ronda de orden por defecto en tablas: "más reciente primero" en toda tabla
 * de los 3 portales, usando el campo de fecha real de cada entidad (no todas
 * se llaman igual: `fecha_envio`, `ts`, `fecha_registro`, etc.).
 *
 * La mayoría de las tablas ya llegan ordenadas así porque el propio backend
 * pagina con `.sort(campo, -1)` -- ahí no hace falta nada acá, es solo
 * cuestión de que la query tenga la dirección correcta. Esta función es para
 * el caso real donde SÍ hace falta ordenar del lado del cliente: una pantalla
 * arma su lista combinando varias respuestas ya ordenadas por separado (ej.
 * "Órdenes abiertas" del panel táctico de Mantenimiento, que concatena 3
 * llamadas por estado) -- la concatenación no preserva un único orden
 * cronológico global, y ahí sí hace falta un sort real del lado del cliente.
 *
 * Centralizada acá (no reinventada por pantalla) para que el criterio de
 * "más reciente" sea siempre el mismo: valores `null`/`undefined`/inválidos
 * quedan al final, nunca arriba simulando ser recientes.
 */
export function ordenarPorFechaDesc<T>(
  filas: T[],
  campo: (fila: T) => string | number | Date | null | undefined,
): T[] {
  return [...filas].sort((a, b) => {
    const va = campo(a);
    const vb = campo(b);
    const ta = va == null ? Number.NEGATIVE_INFINITY : new Date(va).getTime();
    const tb = vb == null ? Number.NEGATIVE_INFINITY : new Date(vb).getTime();
    return tb - ta;
  });
}

/**
 * Tabla compartida por los 3 portales.
 *
 * Grupo C de la ronda de correcciones UX/UI. Antes la única defensa contra
 * una tabla más ancha que su contenedor era `overflowX: auto`: una sola celda
 * larga (un UUID de actor, varios roles concatenados) estiraba su columna sin
 * techo por el layout automático de `<table>`, y la tabla se desbordaba del
 * espacio disponible. Ahora:
 *
 * 1. Toda celda sin `width` explícito trunca con "…" en vez de estirar la
 *    columna (`--table-cell-max-width`, 260px por defecto).
 * 2. Lo truncado se puede consultar completo: al pasar el cursor o tocar la
 *    celda aparece una previsualización con el valor entero. Es genérico,
 *    ningún consumidor tiene que implementarlo por su cuenta.
 * 3. Las columnas pueden declarar `prioridad` y las de menor relevancia se
 *    ocultan en viewports angostos (ver `PrioridadColumna`).
 *
 * El scroll horizontal se mantiene como red de seguridad para el caso en que,
 * aun truncando, las columnas no entren.
 */
export function DataTable<T>({
  columns,
  rows,
  keyField,
  vacio = "Sin resultados",
  altoMaximo,
  ocultarContador,
}: DataTableProps<T>) {
  const [preview, setPreview] = useState<Previsualizacion | null>(null);
  const contenedorRef = useRef<HTMLDivElement>(null);

  // La previsualización abierta por toque se cierra al tocar fuera o con
  // Escape (en escritorio ya se cierra sola al salir la celda con el cursor).
  useEffect(() => {
    if (!preview) return;
    const fuera = (e: MouseEvent) => {
      if (contenedorRef.current && !contenedorRef.current.contains(e.target as Node)) setPreview(null);
    };
    const escape = (e: KeyboardEvent) => {
      if (e.key === "Escape") setPreview(null);
    };
    document.addEventListener("mousedown", fuera);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("mousedown", fuera);
      document.removeEventListener("keydown", escape);
    };
  }, [preview]);

  if (rows.length === 0) {
    return <p style={{ color: "var(--color-text-muted)" }}>{vacio}</p>;
  }

  /** Solo hay algo que previsualizar si el contenido REALMENTE no entra —
   * un badge o un botón corto nunca dispara la previsualización. */
  const abrirSiTruncado = (el: HTMLElement) => {
    const celda = el.querySelector<HTMLElement>(".uf-cell-truncable") ?? el;
    if (celda.scrollWidth <= celda.clientWidth + 1) {
      setPreview(null);
      return;
    }
    const r = celda.getBoundingClientRect();
    setPreview({ texto: celda.innerText, x: r.left, y: r.bottom + 6 });
  };

  return (
    <div ref={contenedorRef} style={{ position: "relative" }}>
      <div
        className={`uf-table-scroll${altoMaximo ? " no-scrollbar" : ""}`}
        style={{ overflowX: "auto", overflowY: altoMaximo ? "auto" : undefined, maxHeight: altoMaximo }}
      >
        {/* El registro: la presentación vive completa en DataTable.css --
            acá solo queda lo que depende de cada columna (ancho declarado,
            prioridad, truncado). */}
        <table className="uf-table">
          <thead>
            <tr>
              {columns.map((c) => (
                <th
                  key={c.header}
                  data-prioridad={c.prioridad ?? "alta"}
                  style={{ width: c.width, textAlign: c.numerica ? "right" : undefined }}
                >
                  {c.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={keyField(row)}>
                {columns.map((c) => {
                  // Con `width` explícito el contenido hace wrap (comportamiento
                  // previo, deliberado); sin él, trunca y se consulta completo
                  // con la previsualización.
                  const trunca = !c.width && !c.sinTruncar;
                  return (
                    <td
                      key={c.header}
                      data-prioridad={c.prioridad ?? "alta"}
                      onMouseEnter={trunca ? (e) => abrirSiTruncado(e.currentTarget) : undefined}
                      onMouseLeave={trunca ? () => setPreview(null) : undefined}
                      onClick={trunca ? (e) => abrirSiTruncado(e.currentTarget) : undefined}
                      style={{
                        width: c.width,
                        maxWidth: c.width,
                        overflowWrap: c.width ? "break-word" : undefined,
                        textAlign: c.numerica ? "right" : undefined,
                        fontVariantNumeric: c.numerica ? "tabular-nums" : undefined,
                      }}
                    >
                      {trunca ? <div className="uf-cell-truncable">{c.render(row)}</div> : c.render(row)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {!ocultarContador && (
        <p style={{ margin: "var(--space-2) 0 0", fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>
          {rows.length} {rows.length === 1 ? "resultado" : "resultados"}
        </p>
      )}

      {preview && (
        <div className="uf-cell-preview" role="tooltip" style={{ left: preview.x, top: preview.y }}>
          {preview.texto}
        </div>
      )}
    </div>
  );
}
