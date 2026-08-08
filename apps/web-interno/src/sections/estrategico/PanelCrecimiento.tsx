import {
  ApiError,
  apiFetch,
  Card,
  DashboardZ,
  DataTable,
  FuenteBadge,
  KpiCard,
  KpiRow,
  Select,
  TrendLineChart,
  useSwr,
} from "@urbanflet/shared-ui";
import { useMemo, useState } from "react";
import { FilaFiltros, NotaLimitacion, TituloTarjeta } from "./comunes";
import { entero, OPCIONES_VENTANA, pct, tonoVariacion, variacion } from "./formato";

// spec: specs/nivel-estrategico/nivel_estrategico.md §3.1 — Panel de
// Crecimiento Estratégico (OE1). Patrón Z.
const RECURSO = "/captacion/panel-estrategico/crecimiento";

// Referencias estables para el fallback de `data?.campo ?? []` — evita que
// los `useMemo` de abajo se invaliden en cada render (mismo patrón que el
// lote 3 del rollout SWR en los paneles tácticos).
const SIN_ALTAS: PuntoAltas[] = [];
const SIN_CONVERSION: PuntoConversion[] = [];
const SIN_ONBOARDING: PuntoOnboarding[] = [];
const SIN_CANALES: CanalCrecimiento[] = [];

interface PuntoAltas {
  periodo: string;
  altas: number;
  pct_retencion: number;
}

interface PuntoConversion {
  periodo: string;
  pct_conversion: number;
  total_solicitudes: number;
}

interface PuntoOnboarding {
  periodo: string;
  pct_activo: number;
  total_registros: number;
}

interface CanalCrecimiento {
  canal: string;
  pct_conversion: number;
  total_solicitudes: number;
  dias_aprobacion_promedio: number | null;
  altas: number;
}

interface PanelCrecimientoOut {
  kpis: {
    pct_conversion_onboarding: number | null;
    pct_retencion_90d: number | null;
    altas_periodo: number | null;
    variacion_altas_pct: number | null;
    crecimiento_demanda_pct: number | null;
  };
  tendencia_altas: PuntoAltas[];
  tendencia_conversion: PuntoConversion[];
  tendencia_onboarding: PuntoOnboarding[];
  canales: CanalCrecimiento[];
  metadata: {
    meses: number;
    canal_cobertura_parcial: boolean;
    demanda_disponible: boolean;
    fuentes: string[];
  };
}

export function PanelCrecimiento() {
  const [meses, setMeses] = useState("12");
  const [filtroCanal, setFiltroCanal] = useState("");

  const clave = `${RECURSO}?meses=${meses}`;
  const { data, error: errorCarga } = useSwr<PanelCrecimientoOut>(clave, () =>
    apiFetch<PanelCrecimientoOut>(clave),
  );
  const error = errorCarga
    ? errorCarga instanceof ApiError
      ? errorCarga.message
      : "No se pudo cargar el panel de crecimiento"
    : null;

  const kpisDatos = data?.kpis;
  const tendenciaAltas = data?.tendencia_altas ?? SIN_ALTAS;
  const tendenciaConversion = data?.tendencia_conversion ?? SIN_CONVERSION;
  const tendenciaOnboarding = data?.tendencia_onboarding ?? SIN_ONBOARDING;
  const canales = data?.canales ?? SIN_CANALES;
  const demandaDisponible = data?.metadata.demanda_disponible ?? false;
  const canalParcial = data?.metadata.canal_cobertura_parcial ?? false;

  // Serie de oferta (altas de socios) y de flujo de captación (solicitudes
  // recibidas), unidas por periodo. Ambas son conteos, así que comparten eje
  // Y sin distorsionar la lectura.
  const serieCrecimiento = useMemo(() => {
    const periodos = Array.from(
      new Set([...tendenciaAltas.map((a) => a.periodo), ...tendenciaConversion.map((c) => c.periodo)]),
    ).sort();
    return periodos.map((periodo) => ({
      periodo,
      altas: tendenciaAltas.find((a) => a.periodo === periodo)?.altas ?? 0,
      solicitudes: tendenciaConversion.find((c) => c.periodo === periodo)?.total_solicitudes ?? 0,
    }));
  }, [tendenciaAltas, tendenciaConversion]);

  const serieOnboarding = useMemo(
    () => tendenciaOnboarding.map((p) => ({ periodo: p.periodo, pct: p.pct_activo * 100 })),
    [tendenciaOnboarding],
  );

  const canalesFiltrados = useMemo(
    () => (filtroCanal ? canales.filter((c) => c.canal === filtroCanal) : canales),
    [canales, filtroCanal],
  );

  const kpis = (
    <>
      <KpiRow>
        <KpiCard etiqueta="Conversión de onboarding" valor={pct(kpisDatos?.pct_conversion_onboarding)} />
        <KpiCard etiqueta="Retención a 90 días" valor={pct(kpisDatos?.pct_retencion_90d)} />
        <KpiCard etiqueta="Altas de socios (periodo)" valor={entero(kpisDatos?.altas_periodo)} />
        <KpiCard
          etiqueta="Variación de altas"
          valor={variacion(kpisDatos?.variacion_altas_pct)}
          tono={tonoVariacion(kpisDatos?.variacion_altas_pct, { subirEsBueno: true })}
        />
        <KpiCard etiqueta="Crecimiento de demanda" valor={pct(kpisDatos?.crecimiento_demanda_pct)} />
      </KpiRow>
      {!demandaDisponible && (
        <NotaLimitacion>
          "Crecimiento de demanda" no disponible — ninguna vista <code>rpt_*</code> publica viajes
          solicitados por mes, y este nivel no consulta MongoDB directo (regla §2 de la spec
          estratégica). Se muestra "—" en vez de sustituirlo por otro indicador.
        </NotaLimitacion>
      )}
    </>
  );

  const grafico = (
    <Card>
      <TituloTarjeta titulo="Tendencia de altas y captación" extra={<FuenteBadge tipo="compuesto" />} />
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
      <TrendLineChart
        datos={serieCrecimiento}
        eje="periodo"
        series={[
          { key: "altas", label: "Altas de socios" },
          { key: "solicitudes", label: "Solicitudes recibidas" },
        ]}
        formatoValor={(v) => entero(v)}
        vacio="Sin historial publicado todavía de altas por periodo."
      />
      <TituloTarjeta titulo="Conversión de onboarding en el tiempo" />
      <TrendLineChart
        datos={serieOnboarding}
        eje="periodo"
        series={[{ key: "pct", label: "% activos" }]}
        formatoValor={(v) => `${v.toFixed(1)}%`}
        alto={200}
        vacio="Sin cortes publicados todavía de onboarding."
      />
    </Card>
  );

  const lista = (
    <Card>
      <TituloTarjeta titulo="Conversión por canal (consolidada)" extra={<FuenteBadge tipo="compuesto" />} />
      <FilaFiltros>
        <div style={{ minWidth: 180 }}>
          <Select
            label="Canal"
            value={filtroCanal}
            onChange={(e) => setFiltroCanal(e.target.value)}
            options={[{ value: "", label: "Todos" }, ...canales.map((c) => ({ value: c.canal, label: c.canal }))]}
          />
        </div>
      </FilaFiltros>
      <DataTable
        rows={canalesFiltrados}
        keyField={(c) => c.canal}
        vacio="Sin datos consolidados de conversión por canal."
        columns={[
          { header: "Canal", render: (c) => c.canal },
          { header: "Conversión", render: (c) => pct(c.pct_conversion) },
          { header: "Solicitudes", render: (c) => entero(c.total_solicitudes) },
          { header: "Altas", render: (c) => entero(c.altas) },
          {
            header: "Días prom. aprobación",
            render: (c) => (c.dias_aprobacion_promedio == null ? "—" : c.dias_aprobacion_promedio.toFixed(2)),
          },
        ]}
      />
      {canalParcial && (
        <NotaLimitacion>
          Cobertura parcial de <strong>canal</strong>: cerca de la mitad de las cuentas del sistema no
          tiene ese campo (hallazgo H3 de la auditoría), así que el desglose por canal subrepresenta a
          esa porción. Los totales de los KPI de arriba sí incluyen a todos.
        </NotaLimitacion>
      )}
    </Card>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
      <h2 style={{ margin: 0 }}>Panel de Crecimiento Estratégico</h2>
      {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
      <DashboardZ kpis={kpis} grafico={grafico} lista={lista} />
    </div>
  );
}
