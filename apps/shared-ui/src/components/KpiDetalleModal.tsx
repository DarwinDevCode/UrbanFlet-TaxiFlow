import type { ReactNode } from "react";
import { Button } from "./Button";
import { DataTable, type Column } from "./DataTable";

interface KpiDetalleModalProps<T> {
  titulo: string;
  onSalir: () => void;
  cargando?: boolean;
  error?: string | null;
  rows: T[];
  keyField: (row: T) => string;
  columns: Column<T>[];
  /** Slot para controles de filtro (Select/TextField), mismo patrón
   * `FilaFiltros` ya usado en los dashboards -- el filtrado real lo hace
   * quien llama, este modal solo renderiza `rows` tal cual se las pasen. */
  filtros?: ReactNode;
  vacio?: string;
}

/**
 * Drill-down real sobre un KPI (ronda de claridad, punto 4 corregido --
 * agosto 2026, ver CLAUDE.md): clic en la tarjeta → modal EN LA MISMA
 * PANTALLA con los registros reales detrás del valor, no navegación a otra
 * sección. Reutiliza el mismo chrome visual que `DetailPanel` (backdrop,
 * tarjeta redondeada, `role="dialog"`) pero sin su semántica de modo/edición
 * -- esto es siempre de solo lectura.
 *
 * Nunca decide qué datos mostrar ni cómo filtrarlos -- `rows`/`columns`/
 * `filtros` los define cada pantalla, mismo principio que `KpiCard`.
 */
export function KpiDetalleModal<T>({
  titulo,
  onSalir,
  cargando,
  error,
  rows,
  keyField,
  columns,
  filtros,
  vacio = "Sin registros con este filtro.",
}: KpiDetalleModalProps<T>) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.4)",
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "center",
        padding: "var(--space-5)",
        overflowY: "auto",
        zIndex: "var(--z-modal)",
      }}
    >
      <div
        style={{
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--radius-lg)",
          boxShadow: "var(--shadow-sm)",
          padding: "var(--space-5)",
          width: "min(920px, 100%)",
          maxHeight: "calc(100vh - var(--space-5) * 2)",
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          gap: "var(--space-4)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "var(--space-3)" }}>
          <h2 style={{ margin: 0, fontSize: "var(--font-size-lg)" }}>{titulo}</h2>
        </div>

        {error && <p style={{ margin: 0, color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}

        {filtros && <div style={{ display: "flex", gap: "var(--space-3)", flexWrap: "wrap" }}>{filtros}</div>}

        {cargando ? (
          <p style={{ color: "var(--color-text-muted)" }}>Cargando…</p>
        ) : (
          <DataTable rows={rows} keyField={keyField} columns={columns} vacio={vacio} altoMaximo={480} />
        )}

        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <div style={{ minWidth: 140 }}>
            <Button variant="secondary" onClick={onSalir}>
              Salir
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

