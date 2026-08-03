import { Button } from "./Button";

interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  onPageSizeChange?: (pageSize: number) => void;
  pageSizeOptions?: number[];
}

/**
 * Controles de paginación (anterior/siguiente, número de página, tamaño de
 * página, total de resultados) para usar debajo de un DataTable. No
 * reimplementa el render de la tabla — solo la navegación limit/offset.
 */
export function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [10, 20, 50],
}: PaginationProps) {
  const totalPaginas = Math.max(1, Math.ceil(total / pageSize));
  const desde = total === 0 ? 0 : page * pageSize + 1;
  const hasta = Math.min(total, (page + 1) * pageSize);

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        flexWrap: "wrap",
        gap: "var(--space-3)",
        marginTop: "var(--space-3)",
        fontSize: "var(--font-size-sm)",
        color: "var(--color-text-muted)",
      }}
    >
      <span>
        {desde}–{hasta} de {total}
      </span>
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
        {onPageSizeChange && (
          <select
            value={pageSize}
            onChange={(e) => onPageSizeChange(Number(e.target.value))}
            style={{ padding: "var(--space-1) var(--space-2)", borderRadius: "var(--radius-sm)", border: "1px solid var(--color-border)" }}
          >
            {pageSizeOptions.map((n) => (
              <option key={n} value={n}>
                {n} / página
              </option>
            ))}
          </select>
        )}
        <div style={{ width: 96 }}>
          <Button variant="secondary" onClick={() => onPageChange(page - 1)} disabled={page <= 0}>
            Anterior
          </Button>
        </div>
        <span>
          Página {page + 1} de {totalPaginas}
        </span>
        <div style={{ width: 96 }}>
          <Button variant="secondary" onClick={() => onPageChange(page + 1)} disabled={page + 1 >= totalPaginas}>
            Siguiente
          </Button>
        </div>
      </div>
    </div>
  );
}
