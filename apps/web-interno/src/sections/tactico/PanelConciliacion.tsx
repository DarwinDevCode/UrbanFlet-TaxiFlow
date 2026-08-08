import {
  ApiError,
  apiFetch,
  Badge,
  Card,
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

const RECURSO_PANEL_CONCILIACION = "/pagos/panel-tactico";

// Ver PanelMantenimiento.tsx: referencia estable para el fallback de
// `data?.campo ?? []`/objeto, evita invalidar los `useMemo` que dependen
// de esto.
const SIN_BANDEJA: BandejaDiscrepancias = { discrepancias: [], viajes_sin_pago: [] };
const SIN_TASAS: TasaDiscrepancias[] = [];

interface Pago {
  id: string;
  viaje_id: string;
  conductor_nombre: string | null;
  metodo: string;
  monto: number;
  diferencia: number | null;
  estado: string;
  ts_registro: string;
}

interface ViajeSinPago {
  viaje_id: string;
  conductor_nombre: string | null;
  tarifa_final: number;
  ts_fin: string;
}

interface BandejaDiscrepancias {
  discrepancias: Pago[];
  viajes_sin_pago: ViajeSinPago[];
}

interface TasaDiscrepancias {
  fecha_periodo: string;
  metodo: string;
  pct_discrepancia: number;
  pct_conciliado: number;
  total_registros: number;
}

// spec: specs/nivel-tactico/tactico_finanzas.md — Panel de Conciliación de Pagos (CU-T09/OT5.1). Patrón Z.
interface DatosPanelConciliacion {
  bandeja: BandejaDiscrepancias;
  tasas: TasaDiscrepancias[];
}

export function PanelConciliacion() {
  const [filtroMetodo, setFiltroMetodo] = useState("");
  const [filtroDesde, setFiltroDesde] = useState("");
  const [filtroHasta, setFiltroHasta] = useState("");

  const { data, error: errorCarga } = useSwr<DatosPanelConciliacion>(RECURSO_PANEL_CONCILIACION, async () => {
    const [b, t] = await Promise.all([
      apiFetch<BandejaDiscrepancias>("/pagos/discrepancias"),
      apiFetch<TasaDiscrepancias[]>("/pagos/panel-tactico/tasa-discrepancias"),
    ]);
    return { bandeja: b, tasas: t };
  });
  const bandeja = data?.bandeja ?? SIN_BANDEJA;
  const tasas = data?.tasas ?? SIN_TASAS;
  const error = errorCarga
    ? errorCarga instanceof ApiError
      ? errorCarga.message
      : "No se pudo cargar el panel de conciliación"
    : null;

  const montoEnDisputa = useMemo(
    () => bandeja.discrepancias.reduce((acc, p) => acc + Math.abs(p.diferencia ?? 0), 0),
    [bandeja.discrepancias],
  );
  const pctConciliadoPromedio = tasas.length ? tasas.reduce((acc, t) => acc + t.pct_conciliado, 0) / tasas.length : null;

  const metodosDisponibles = useMemo(
    () => Array.from(new Set(bandeja.discrepancias.map((p) => p.metodo))).sort(),
    [bandeja.discrepancias],
  );
  const discrepanciasFiltradas = useMemo(() => {
    return bandeja.discrepancias.filter((p) => {
      if (filtroMetodo && p.metodo !== filtroMetodo) return false;
      const fecha = p.ts_registro.slice(0, 10);
      if (filtroDesde && fecha < filtroDesde) return false;
      if (filtroHasta && fecha > filtroHasta) return false;
      return true;
    });
  }, [bandeja.discrepancias, filtroMetodo, filtroDesde, filtroHasta]);
  const sinPagoFiltrados = useMemo(() => {
    return bandeja.viajes_sin_pago.filter((v) => {
      const fecha = v.ts_fin.slice(0, 10);
      if (filtroDesde && fecha < filtroDesde) return false;
      if (filtroHasta && fecha > filtroHasta) return false;
      return true;
    });
  }, [bandeja.viajes_sin_pago, filtroDesde, filtroHasta]);

  const periodos = useMemo(() => Array.from(new Set(tasas.map((t) => t.fecha_periodo.slice(0, 7)))).sort(), [tasas]);
  const metodosTasa = useMemo(() => Array.from(new Set(tasas.map((t) => t.metodo))), [tasas]);
  const tasasPivot = useMemo(
    () =>
      periodos.map((periodo) => {
        const fila: Record<string, string | number> = { periodo };
        for (const metodo of metodosTasa) {
          const dato = tasas.find((t) => t.fecha_periodo.slice(0, 7) === periodo && t.metodo === metodo);
          if (dato) fila[metodo] = dato.pct_discrepancia * 100;
        }
        return fila;
      }),
    [periodos, metodosTasa, tasas],
  );

  const kpis = (
    <KpiRow>
      <KpiCard etiqueta="Discrepancias" valor={String(bandeja.discrepancias.length)} tono={bandeja.discrepancias.length > 0 ? "peligro" : undefined} />
      <KpiCard etiqueta="Monto en disputa" valor={`$${montoEnDisputa.toFixed(2)}`} />
      <KpiCard etiqueta="% conciliado" valor={pctConciliadoPromedio != null ? `${(pctConciliadoPromedio * 100).toFixed(1)}%` : "—"} />
      <KpiCard etiqueta="Viajes sin pago" valor={String(bandeja.viajes_sin_pago.length)} tono={bandeja.viajes_sin_pago.length > 0 ? "advertencia" : undefined} />
    </KpiRow>
  );

  const grafico = (
    <Card>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-3)" }}>
        <h3 style={{ margin: 0, fontSize: "var(--font-size-md)" }}>Tasa de discrepancias mensual</h3>
        <FuenteBadge tipo="compuesto" />
      </div>
      <TrendLineChart
        datos={tasasPivot}
        eje="periodo"
        series={metodosTasa.map((m) => ({ key: m, label: m }))}
        formatoValor={(v) => `${v.toFixed(1)}%`}
        vacio="Sin datos publicados todavía de tasa de discrepancias."
      />
    </Card>
  );

  const lista = (
    <Card>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-3)" }}>
        <h3 style={{ margin: 0, fontSize: "var(--font-size-md)" }}>Discrepancias abiertas</h3>
        <FuenteBadge tipo="simple" />
      </div>
      <div style={{ display: "flex", gap: "var(--space-3)", flexWrap: "wrap", marginBottom: "var(--space-4)" }}>
        <div style={{ minWidth: 160 }}>
          <Select
            label="Método de pago"
            value={filtroMetodo}
            onChange={(e) => setFiltroMetodo(e.target.value)}
            options={[{ value: "", label: "Todos" }, ...metodosDisponibles.map((m) => ({ value: m, label: m }))]}
          />
        </div>
        <div style={{ minWidth: 150 }}>
          <TextField label="Desde" type="date" value={filtroDesde} onChange={(e) => setFiltroDesde(e.target.value)} />
        </div>
        <div style={{ minWidth: 150 }}>
          <TextField label="Hasta" type="date" value={filtroHasta} onChange={(e) => setFiltroHasta(e.target.value)} />
        </div>
      </div>
      <DataTable
        rows={discrepanciasFiltradas}
        keyField={(p) => p.id}
        vacio="No hay discrepancias abiertas con este filtro."
        columns={[
          { header: "Conductor", render: (p) => p.conductor_nombre ?? p.viaje_id.slice(0, 8) },
          { header: "Método", render: (p) => p.metodo },
          { header: "Monto", render: (p) => `$${p.monto.toFixed(2)}` },
          { header: "Diferencia", render: (p) => (p.diferencia != null ? `$${p.diferencia.toFixed(2)}` : "—") },
          { header: "Estado", render: (p) => <Badge texto={p.estado} tono="peligro" /> },
          { header: "Registrado", render: (p) => new Date(p.ts_registro).toLocaleString() },
        ]}
      />
      <h4 style={{ margin: "var(--space-4) 0 var(--space-2)" }}>Viajes sin pago</h4>
      <DataTable
        rows={sinPagoFiltrados}
        keyField={(v) => v.viaje_id}
        vacio="No hay viajes finalizados sin pago registrado con este filtro."
        columns={[
          { header: "Conductor", render: (v) => v.conductor_nombre ?? v.viaje_id.slice(0, 8) },
          { header: "Tarifa final", render: (v) => `$${v.tarifa_final.toFixed(2)}` },
          { header: "Finalizado", render: (v) => new Date(v.ts_fin).toLocaleString() },
        ]}
      />
    </Card>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
      <h2 style={{ margin: 0 }}>Panel de Conciliación de Pagos</h2>
      {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
      <DashboardZ kpis={kpis} grafico={grafico} lista={lista} />
    </div>
  );
}
