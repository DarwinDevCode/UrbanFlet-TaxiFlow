import type { ReactNode } from "react";

interface Column<T> {
  header: string;
  render: (row: T) => ReactNode;
  /** Ancho CSS fijo (ej. "140px") -- evita que una celda con contenido
   * inusualmente largo (ej. varios roles separados por coma en un mismo
   * evento) estire la columna entera vía el layout automático de <table>.
   * El contenido de esa celda hace wrap dentro del ancho, no se trunca. */
  width?: string;
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
}

export function DataTable<T>({ columns, rows, keyField, vacio = "Sin resultados", altoMaximo }: DataTableProps<T>) {
  if (rows.length === 0) {
    return <p style={{ color: "var(--color-text-muted)" }}>{vacio}</p>;
  }

  return (
    <div style={{ overflowX: "auto", overflowY: altoMaximo ? "auto" : undefined, maxHeight: altoMaximo }}>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr>
            {columns.map((c) => (
              <th
                key={c.header}
                style={{
                  textAlign: "left",
                  padding: "var(--table-cell-padding-y, var(--space-2)) var(--table-cell-padding-x, var(--space-3))",
                  borderBottom: "1px solid var(--color-border)",
                  color: "var(--color-text-muted)",
                  fontSize: "var(--font-size-sm)",
                  fontWeight: 600,
                  whiteSpace: "nowrap",
                  width: c.width,
                }}
              >
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={keyField(row)}>
              {columns.map((c) => (
                <td
                  key={c.header}
                  style={{
                    padding: "var(--table-cell-padding-y, var(--space-2)) var(--table-cell-padding-x, var(--space-3))",
                    borderBottom: "1px solid var(--color-border)",
                    width: c.width,
                    maxWidth: c.width,
                    overflowWrap: c.width ? "break-word" : undefined,
                  }}
                >
                  {c.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
