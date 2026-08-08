import {
  ApiError,
  apiFetch,
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
import { FilaFiltros, NotaLimitacion, TituloTarjeta } from "./comunes";
import { entero, moneda, OPCIONES_VENTANA, pct, tonoVariacion, variacion } from "./formato";

// spec: specs/nivel-estrategico/nivel_estrategico.md §3.2.b — Panel de
// Estado y Costo de Flota (OE2b). Patrón Z.
const RECURSO = "/mantenimiento/panel-estrategico/estado-costo-flota";

const SIN_PREVENTIVO: PuntoPreventivo[] = [];
const SIN_COSTO: PuntoCosto[] = [];
const SIN_CANDIDATOS: CandidatoReemplazo[] = [];

interface PuntoPreventivo {
  periodo: string;
  pct_cumplimiento: number;
  total_ordenes: number;
}

interface PuntoCosto {
  periodo: string;
  costo_total: number;
  total_ordenes: number;
}

interface CandidatoReemplazo {
  vehiculo_id: string;
  vehiculo_placa: string | null;
  costo_total: number;
  costo_promedio_mes: number | null;
  total_ordenes: number;
  periodos: number;
  km_recorridos: number | null;
}

interface PanelEstadoCostoFlotaOut {
  kpis: {
    pct_cumplimiento_preventivo: number | null;
    variacion_cumplimiento_pct: number | null;
    costo_mantenimiento_periodo: number | null;
    variacion_costo_pct: number | null;
    costo_acumulado: number | null;
  };
  tendencia_preventivo: PuntoPreventivo[];
  tendencia_costo: PuntoCosto[];
  candidatos_reemplazo: CandidatoReemplazo[];
  metadata: { meses: number; km_disponible: boolean; fuentes: string[] };
}

export function PanelEstadoCostoFlota() {
  const [meses, setMeses] = useState("12");
  const [busquedaVehiculo, setBusquedaVehiculo] = useState("");

  const clave = `${RECURSO}?meses=${meses}`;
  const { data, error: errorCarga } = useSwr<PanelEstadoCostoFlotaOut>(clave, () =>
    apiFetch<PanelEstadoCostoFlotaOut>(clave),
  );
  const error = errorCarga
    ? errorCarga instanceof ApiError
      ? errorCarga.message
      : "No se pudo cargar el panel de estado y costo de flota"
    : null;

  const k = data?.kpis;
  const tendenciaPreventivo = data?.tendencia_preventivo ?? SIN_PREVENTIVO;
  const tendenciaCosto = data?.tendencia_costo ?? SIN_COSTO;
  const candidatos = data?.candidatos_reemplazo ?? SIN_CANDIDATOS;
  const kmDisponible = data?.metadata.km_disponible ?? false;

  const seriePreventivo = useMemo(
    () => tendenciaPreventivo.map((p) => ({ periodo: p.periodo, pct: p.pct_cumplimiento * 100 })),
    [tendenciaPreventivo],
  );

  const candidatosFiltrados = useMemo(() => {
    const texto = busquedaVehiculo.trim().toLowerCase();
    if (!texto) return candidatos;
    return candidatos.filter(
      (c) => (c.vehiculo_placa ?? "").toLowerCase().includes(texto) || c.vehiculo_id.toLowerCase().includes(texto),
    );
  }, [candidatos, busquedaVehiculo]);

  const kpis = (
    <KpiRow>
      <KpiCard
        etiqueta="Cumplimiento preventivo"
        valor={pct(k?.pct_cumplimiento_preventivo)}
        tono={
          k?.pct_cumplimiento_preventivo != null && k.pct_cumplimiento_preventivo < 0.8 ? "advertencia" : undefined
        }
      />
      <KpiCard
        etiqueta="Variación cumplimiento"
        valor={variacion(k?.variacion_cumplimiento_pct)}
        tono={tonoVariacion(k?.variacion_cumplimiento_pct, { subirEsBueno: true })}
      />
      <KpiCard etiqueta="Costo del último periodo" valor={moneda(k?.costo_mantenimiento_periodo)} />
      <KpiCard
        etiqueta="Variación de costo"
        valor={variacion(k?.variacion_costo_pct)}
        tono={tonoVariacion(k?.variacion_costo_pct, { subirEsBueno: false })}
      />
      <KpiCard etiqueta="Costo acumulado" valor={moneda(k?.costo_acumulado)} />
    </KpiRow>
  );

  const grafico = (
    <Card>
      <TituloTarjeta titulo="Costo total de mantenimiento por mes" extra={<FuenteBadge tipo="compuesto" />} />
      <FilaFiltros>
        <div style={{ minWidth: 180 }}>
          <Select
            label="Ventana (meses)"
            value={meses}
            onChange={(e) => setMeses(e.target.value)}
            options={OPCIONES_VENTANA}
          />
        </div>
      </FilaFiltros>
      <CategoryBarChart
        datos={tendenciaCosto}
        categoria="periodo"
        series={[{ key: "costo_total", label: "Costo total" }]}
        formatoValor={(v) => moneda(v, 0)}
        vacio="Sin costos publicados todavía para esta ventana."
      />
      <TituloTarjeta titulo="Cumplimiento del plan preventivo (%)" />
      <TrendLineChart
        datos={seriePreventivo}
        eje="periodo"
        series={[{ key: "pct", label: "% cumplimiento" }]}
        formatoValor={(v) => `${v.toFixed(1)}%`}
        alto={200}
        vacio="Sin cortes publicados todavía de cumplimiento preventivo."
      />
    </Card>
  );

  const lista = (
    <Card>
      <TituloTarjeta titulo="Vehículos candidatos a reemplazo" extra={<FuenteBadge tipo="compuesto" />} />
      <FilaFiltros>
        <div style={{ minWidth: 220 }}>
          <TextField
            label="Vehículo (placa o id)"
            value={busquedaVehiculo}
            onChange={(e) => setBusquedaVehiculo(e.target.value)}
          />
        </div>
      </FilaFiltros>
      <DataTable
        rows={candidatosFiltrados}
        keyField={(c) => c.vehiculo_id}
        vacio="Sin vehículos con costo acumulado en esta ventana."
        columns={[
          { header: "Placa", render: (c) => c.vehiculo_placa ?? c.vehiculo_id.slice(0, 8) + "…" },
          { header: "Costo acumulado", render: (c) => moneda(c.costo_total) },
          { header: "Costo prom./mes", render: (c) => moneda(c.costo_promedio_mes) },
          { header: "Órdenes", render: (c) => entero(c.total_ordenes) },
          { header: "Meses con costo", render: (c) => entero(c.periodos) },
          { header: "Km recorridos", render: (c) => (c.km_recorridos == null ? "—" : entero(c.km_recorridos)) },
        ]}
      />
      {!kmDisponible && (
        <NotaLimitacion>
          "Costo vs. km recorridos" que pide la spec queda a medias: el <strong>kilometraje</strong> no
          existe en ninguna vista <code>rpt_*</code> y este nivel no consulta MongoDB directo (regla §2),
          así que la columna se muestra en "—". La comparación se hace por costo acumulado y costo
          promedio por mes.
        </NotaLimitacion>
      )}
    </Card>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
      <h2 style={{ margin: 0 }}>Panel de Estado y Costo de Flota</h2>
      {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
      <DashboardZ kpis={kpis} grafico={grafico} lista={lista} />
    </div>
  );
}
