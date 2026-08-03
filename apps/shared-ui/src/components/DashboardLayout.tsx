import type { ReactNode } from "react";
import "./DashboardLayout.css";

/**
 * Patrón Z (specs/nivel-tactico/): KPIs en fila superior (lectura
 * horizontal), luego gráfico a la izquierda y lista/detalle a la derecha en
 * la misma fila — el trazo Z requiere que el segundo bloque esté al costado,
 * no apilado debajo. En pantallas angostas colapsa a una columna.
 */
export function DashboardZ({
  kpis,
  grafico,
  lista,
}: {
  kpis: ReactNode;
  grafico: ReactNode;
  lista: ReactNode;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
      {kpis}
      <div
        className="dashboard-z-row"
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)",
          gap: "var(--space-5)",
          alignItems: "start",
        }}
      >
        {grafico}
        {lista}
      </div>
    </div>
  );
}

/**
 * Patrón F (solo Auditoría e Integraciones de los 9): la tabla/lista es el
 * elemento dominante en ancho y altura; los KPIs quedan como franja delgada
 * de contexto arriba, no como tarjetas grandes; el gráfico secundario es más
 * angosto que la lista, no ocupa la mitad de la fila como en Z.
 */
export function DashboardF({
  kpis,
  grafico,
  lista,
}: {
  kpis: ReactNode;
  grafico: ReactNode;
  lista: ReactNode;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      {kpis}
      <div
        className="dashboard-f-row"
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 320px) minmax(0, 1fr)",
          gap: "var(--space-5)",
          alignItems: "start",
        }}
      >
        {grafico}
        {lista}
      </div>
    </div>
  );
}
