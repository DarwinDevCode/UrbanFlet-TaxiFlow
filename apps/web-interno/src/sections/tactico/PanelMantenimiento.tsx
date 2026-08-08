import {
  ApiError,
  apiFetch,
  Badge,
  Card,
  CategoryBarChart,
  DashboardZ,
  DataTable,
  FuenteBadge,
  KpiCard,
  KpiRow,
  Select,
  TextField,
  TrendLineChart,
  useSwr,
} from "@urbanflet/shared-ui";
import { useMemo, useState } from "react";

const RECURSO_PANEL_MANTENIMIENTO = "/mantenimiento/panel-tactico";

// Referencias estables para el fallback de `data?.campo ?? []` -- un array
// literal `[]` inline crea una referencia nueva en cada render, lo que
// invalidaba la memoización de los `useMemo` que dependen de estos campos.
const SIN_ORDENES: Orden[] = [];
const SIN_RETIRADOS: VehiculoRetirado[] = [];
const SIN_PREVENTIVO: CumplimientoPreventivo[] = [];
const SIN_COSTO_TOP: CostoVehiculo[] = [];

interface Orden {
  id: string;
  vehiculo_id: string;
  vehiculo_placa: string | null;
  tipo: "PREVENTIVA" | "CORRECTIVA";
  estado: string;
  fecha_programada: string;
  taller: string;
}

interface OrdenListOut {
  items: Orden[];
  total: number;
}

interface VehiculoRetirado {
  vehiculo_id: string;
  placa: string;
  orden_id: string | null;
  orden_estado: string | null;
  fecha_programada: string | null;
}

interface CumplimientoPreventivo {
  periodo: string;
  pct_cumplimiento: number;
  total_ordenes: number;
}

interface CostoVehiculo {
  vehiculo_id: string;
  vehiculo_placa: string | null;
  periodo: string;
  costo_total: number;
  total_ordenes: number;
}

interface DatosPanelMantenimiento {
  ordenesAbiertas: Orden[];
  retirados: VehiculoRetirado[];
  preventivo: CumplimientoPreventivo[];
  costoTop: CostoVehiculo[];
}

// spec: specs/nivel-tactico/tactico_mantenimiento.md — Panel de Mantenimiento y Costos (CU-T04/T11). Patrón Z.
export function PanelMantenimiento() {
  const [filtroTipo, setFiltroTipo] = useState("");
  const [filtroVehiculo, setFiltroVehiculo] = useState("");
  const [filtroDesde, setFiltroDesde] = useState("");
  const [filtroHasta, setFiltroHasta] = useState("");

  const { data, error: errorCarga } = useSwr<DatosPanelMantenimiento>(RECURSO_PANEL_MANTENIMIENTO, async () => {
    const [abiertas, enTaller, vehiculosRetirados, cumplimiento, costos] = await Promise.all([
      apiFetch<OrdenListOut>("/mantenimiento/ordenes?estado=ABIERTA&limit=100"),
      apiFetch<OrdenListOut>("/mantenimiento/ordenes?estado=EN_TALLER&limit=100"),
      apiFetch<VehiculoRetirado[]>("/mantenimiento/panel-tactico/vehiculos-retirados"),
      apiFetch<CumplimientoPreventivo[]>("/mantenimiento/panel-tactico/cumplimiento-preventivo"),
      apiFetch<CostoVehiculo[]>("/mantenimiento/panel-tactico/costo-top-vehiculos"),
    ]);
    return {
      ordenesAbiertas: [...abiertas.items, ...enTaller.items],
      retirados: vehiculosRetirados,
      preventivo: cumplimiento,
      costoTop: costos,
    };
  });
  const ordenesAbiertas = data?.ordenesAbiertas ?? SIN_ORDENES;
  const retirados = data?.retirados ?? SIN_RETIRADOS;
  const preventivo = data?.preventivo ?? SIN_PREVENTIVO;
  const costoTop = data?.costoTop ?? SIN_COSTO_TOP;
  const error = errorCarga
    ? errorCarga instanceof ApiError
      ? errorCarga.message
      : "No se pudo cargar el panel de mantenimiento"
    : null;

  const ordenesFiltradas = useMemo(() => {
    return ordenesAbiertas.filter((o) => {
      if (filtroTipo && o.tipo !== filtroTipo) return false;
      if (filtroVehiculo && !(o.vehiculo_placa ?? "").toLowerCase().includes(filtroVehiculo.toLowerCase())) return false;
      const fecha = o.fecha_programada.slice(0, 10);
      if (filtroDesde && fecha < filtroDesde) return false;
      if (filtroHasta && fecha > filtroHasta) return false;
      return true;
    });
  }, [ordenesAbiertas, filtroTipo, filtroVehiculo, filtroDesde, filtroHasta]);

  const ultimoPeriodo = preventivo.at(-1);
  const costoDelMes = costoTop.reduce((acc, c) => acc + c.costo_total, 0);

  const kpis = (
    <KpiRow>
      <KpiCard etiqueta="Órdenes abiertas" valor={String(ordenesAbiertas.length)} />
      <KpiCard etiqueta="Vehículos retirados" valor={String(retirados.length)} tono={retirados.length > 0 ? "advertencia" : undefined} />
      <KpiCard
        etiqueta="Cumplimiento preventivo"
        valor={ultimoPeriodo ? `${(ultimoPeriodo.pct_cumplimiento * 100).toFixed(1)}%` : "—"}
      />
      <KpiCard etiqueta="Costo acumulado (top 5)" valor={`$${costoDelMes.toFixed(2)}`} />
    </KpiRow>
  );

  const grafico = (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
      <Card>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-3)" }}>
          <h3 style={{ margin: 0, fontSize: "var(--font-size-md)" }}>Costo de mantenimiento por vehículo (top 5)</h3>
          <FuenteBadge tipo="compuesto" />
        </div>
        <CategoryBarChart
          datos={costoTop.map((c) => ({ vehiculo: c.vehiculo_placa ?? c.vehiculo_id.slice(0, 8), costo: c.costo_total }))}
          categoria="vehiculo"
          series={[{ key: "costo", label: "Costo total" }]}
          formatoValor={(v) => `$${v.toFixed(2)}`}
          vacio="Sin datos publicados todavía de costo por vehículo."
          alto={220}
        />
      </Card>
      <Card>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-3)" }}>
          <h3 style={{ margin: 0, fontSize: "var(--font-size-md)" }}>Cumplimiento del plan preventivo por mes</h3>
          <FuenteBadge tipo="compuesto" />
        </div>
        <TrendLineChart
          datos={preventivo.map((p) => ({ periodo: p.periodo, pct: p.pct_cumplimiento * 100 }))}
          eje="periodo"
          series={[{ key: "pct", label: "% cumplimiento" }]}
          formatoValor={(v) => `${v.toFixed(1)}%`}
          vacio="Sin datos publicados todavía de cumplimiento preventivo."
          alto={220}
        />
      </Card>
    </div>
  );

  const lista = (
    <Card>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-3)" }}>
        <h3 style={{ margin: 0, fontSize: "var(--font-size-md)" }}>Órdenes abiertas y vehículos retirados de servicio</h3>
        <FuenteBadge tipo="simple" />
      </div>
      <div style={{ display: "flex", gap: "var(--space-3)", flexWrap: "wrap", marginBottom: "var(--space-4)" }}>
        <div style={{ minWidth: 160 }}>
          <Select
            label="Tipo de orden"
            value={filtroTipo}
            onChange={(e) => setFiltroTipo(e.target.value)}
            options={[
              { value: "", label: "Todas" },
              { value: "PREVENTIVA", label: "Preventiva" },
              { value: "CORRECTIVA", label: "Correctiva" },
            ]}
          />
        </div>
        <div style={{ minWidth: 160 }}>
          <TextField label="Vehículo (placa)" value={filtroVehiculo} onChange={(e) => setFiltroVehiculo(e.target.value)} />
        </div>
        <div style={{ minWidth: 150 }}>
          <TextField label="Desde" type="date" value={filtroDesde} onChange={(e) => setFiltroDesde(e.target.value)} />
        </div>
        <div style={{ minWidth: 150 }}>
          <TextField label="Hasta" type="date" value={filtroHasta} onChange={(e) => setFiltroHasta(e.target.value)} />
        </div>
      </div>
      <DataTable
        rows={ordenesFiltradas}
        keyField={(o) => o.id}
        vacio="No hay órdenes abiertas con este filtro."
        columns={[
          { header: "Vehículo", render: (o) => o.vehiculo_placa ?? o.vehiculo_id.slice(0, 8) },
          { header: "Tipo", render: (o) => o.tipo },
          { header: "Estado", render: (o) => <Badge texto={o.estado} tono={o.estado === "EN_TALLER" ? "advertencia" : "neutral"} /> },
          { header: "Taller", render: (o) => o.taller },
          { header: "Fecha programada", render: (o) => new Date(o.fecha_programada).toLocaleDateString() },
        ]}
      />
      <h4 style={{ margin: "var(--space-4) 0 var(--space-2)" }}>Vehículos retirados de servicio</h4>
      <DataTable
        rows={retirados}
        keyField={(v) => v.vehiculo_id}
        vacio="No hay vehículos retirados de servicio."
        columns={[
          { header: "Vehículo", render: (v) => v.placa },
          { header: "Orden que lo retiene", render: (v) => v.orden_id?.slice(0, 8) ?? "—" },
          { header: "Estado de la orden", render: (v) => (v.orden_estado ? <Badge texto={v.orden_estado} tono="advertencia" /> : "—") },
          {
            header: "Fecha programada",
            render: (v) => (v.fecha_programada ? new Date(v.fecha_programada).toLocaleDateString() : "—"),
          },
        ]}
      />
    </Card>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
      <h2 style={{ margin: 0 }}>Panel de Mantenimiento y Costos</h2>
      {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
      <DashboardZ kpis={kpis} grafico={grafico} lista={lista} />
    </div>
  );
}
