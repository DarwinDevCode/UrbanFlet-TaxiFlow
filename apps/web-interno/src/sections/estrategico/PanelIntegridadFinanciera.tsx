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
  TrendLineChart,
  useSwr,
} from "@urbanflet/shared-ui";
import { useMemo, useState } from "react";
import { FilaFiltros, NotaLimitacion, TituloTarjeta } from "./comunes";
import { entero, OPCIONES_VENTANA, pct, tonoVariacion, variacion } from "./formato";

// spec: specs/nivel-estrategico/nivel_estrategico.md §3.5 — Panel de
// Integridad Financiera (OE5 / CU-E04). Patrón Z.
const RECURSO = "/liquidaciones/panel-estrategico/integridad-financiera";

const SIN_CONCILIACION: PuntoConciliacion[] = [];
const SIN_MARGEN: PuntoMargen[] = [];
const SIN_INTERANUAL: ComparacionInteranual[] = [];

interface PuntoConciliacion {
  periodo: string;
  pct_conciliado: number;
  pct_discrepancia: number;
  total_registros: number;
}

interface PuntoMargen {
  periodo: string;
  margen: number;
  bruto_total: number;
  comisiones_total: number;
}

interface ComparacionInteranual {
  anio: string;
  pct_conciliado: number;
  total_registros: number;
}

interface PanelIntegridadFinancieraOut {
  kpis: {
    pct_conciliado: number | null;
    variacion_conciliado_pct: number | null;
    tasa_discrepancias: number | null;
    variacion_discrepancias_pct: number | null;
    margen_comision_promedio: number | null;
  };
  tendencia_conciliacion: PuntoConciliacion[];
  tendencia_margen: PuntoMargen[];
  periodos_con_discrepancia: PuntoConciliacion[];
  interanual: ComparacionInteranual[];
  metadata: { meses: number; interanual_disponible: boolean; dataset_mixto: boolean; fuentes: string[] };
}

export function PanelIntegridadFinanciera() {
  const [meses, setMeses] = useState("12");
  const [filtroAnio, setFiltroAnio] = useState("");

  const clave = `${RECURSO}?meses=${meses}`;
  const { data, error: errorCarga } = useSwr<PanelIntegridadFinancieraOut>(clave, () =>
    apiFetch<PanelIntegridadFinancieraOut>(clave),
  );
  const error = errorCarga
    ? errorCarga instanceof ApiError
      ? errorCarga.message
      : "No se pudo cargar el panel de integridad financiera"
    : null;

  const k = data?.kpis;
  const tendenciaConciliacion = data?.tendencia_conciliacion ?? SIN_CONCILIACION;
  const tendenciaMargen = data?.tendencia_margen ?? SIN_MARGEN;
  const periodosConDiscrepancia = data?.periodos_con_discrepancia ?? SIN_CONCILIACION;
  const interanual = data?.interanual ?? SIN_INTERANUAL;
  const datasetMixto = data?.metadata.dataset_mixto ?? false;
  const interanualDisponible = data?.metadata.interanual_disponible ?? false;

  const anios = useMemo(
    () => Array.from(new Set(tendenciaConciliacion.map((p) => p.periodo.slice(0, 4)))).sort(),
    [tendenciaConciliacion],
  );
  const conciliacionFiltrada = useMemo(
    () =>
      filtroAnio ? tendenciaConciliacion.filter((p) => p.periodo.startsWith(filtroAnio)) : tendenciaConciliacion,
    [tendenciaConciliacion, filtroAnio],
  );
  const serieConciliacion = useMemo(
    () =>
      conciliacionFiltrada.map((p) => ({
        periodo: p.periodo,
        conciliado: p.pct_conciliado * 100,
        discrepancia: p.pct_discrepancia * 100,
      })),
    [conciliacionFiltrada],
  );
  const serieMargen = useMemo(
    () => tendenciaMargen.map((p) => ({ periodo: p.periodo, pct: p.margen * 100 })),
    [tendenciaMargen],
  );
  const interanualGrafico = useMemo(
    () => interanual.map((p) => ({ anio: p.anio, pct: p.pct_conciliado * 100 })),
    [interanual],
  );
  const discrepanciasFiltradas = useMemo(
    () =>
      filtroAnio
        ? periodosConDiscrepancia.filter((p) => p.periodo.startsWith(filtroAnio))
        : periodosConDiscrepancia,
    [periodosConDiscrepancia, filtroAnio],
  );

  const kpis = (
    <KpiRow>
      <KpiCard
        etiqueta="Conciliado"
        valor={pct(k?.pct_conciliado)}
        tono={k?.pct_conciliado != null && k.pct_conciliado < 1 ? "advertencia" : "exito"}
      />
      <KpiCard
        etiqueta="Variación conciliación"
        valor={variacion(k?.variacion_conciliado_pct)}
        tono={tonoVariacion(k?.variacion_conciliado_pct, { subirEsBueno: true })}
      />
      <KpiCard
        etiqueta="Tasa de discrepancias"
        valor={pct(k?.tasa_discrepancias)}
        tono={k?.tasa_discrepancias != null && k.tasa_discrepancias > 0 ? "peligro" : undefined}
      />
      <KpiCard
        etiqueta="Variación discrepancias"
        valor={variacion(k?.variacion_discrepancias_pct)}
        tono={tonoVariacion(k?.variacion_discrepancias_pct, { subirEsBueno: false })}
      />
      <KpiCard etiqueta="Margen de comisión prom." valor={pct(k?.margen_comision_promedio)} />
    </KpiRow>
  );

  const grafico = (
    <Card>
      <TituloTarjeta titulo="Conciliación y discrepancias en el tiempo" extra={<FuenteBadge tipo="compuesto" />} />
      <FilaFiltros>
        <div style={{ minWidth: 180 }}>
          <Select
            label="Ventana (meses)"
            value={meses}
            onChange={(e) => setMeses(e.target.value)}
            options={OPCIONES_VENTANA}
          />
        </div>
        <div style={{ minWidth: 150 }}>
          <Select
            label="Año"
            value={filtroAnio}
            onChange={(e) => setFiltroAnio(e.target.value)}
            options={[{ value: "", label: "Todos" }, ...anios.map((a) => ({ value: a, label: a }))]}
          />
        </div>
      </FilaFiltros>
      <TrendLineChart
        datos={serieConciliacion}
        eje="periodo"
        series={[
          { key: "conciliado", label: "% conciliado" },
          { key: "discrepancia", label: "% discrepancia" },
        ]}
        formatoValor={(v) => `${v.toFixed(1)}%`}
        vacio="Sin periodos publicados todavía de conciliación."
      />
      <TituloTarjeta titulo="Margen de comisión (%)" />
      <TrendLineChart
        datos={serieMargen}
        eje="periodo"
        series={[{ key: "pct", label: "Margen" }]}
        formatoValor={(v) => `${v.toFixed(1)}%`}
        alto={200}
        vacio="Sin periodos publicados todavía de margen de comisión."
      />
    </Card>
  );

  const lista = (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
      <Card>
        <TituloTarjeta titulo="Periodos con discrepancia relevante" extra={<FuenteBadge tipo="compuesto" />} />
        <DataTable
          rows={discrepanciasFiltradas}
          keyField={(p) => p.periodo}
          vacio="Ningún periodo con discrepancia relevante en esta ventana."
          columns={[
            { header: "Periodo", render: (p) => p.periodo },
            {
              header: "% conciliado",
              render: (p) => (
                <Badge
                  texto={pct(p.pct_conciliado)}
                  tono={p.pct_conciliado >= 0.99 ? "exito" : p.pct_conciliado >= 0.9 ? "advertencia" : "peligro"}
                />
              ),
            },
            { header: "% discrepancia", render: (p) => pct(p.pct_discrepancia) },
            { header: "Registros", render: (p) => entero(p.total_registros) },
          ]}
        />
      </Card>

      <Card>
        <TituloTarjeta titulo="Comparación interanual" extra={<FuenteBadge tipo="compuesto" />} />
        {interanualDisponible ? (
          <CategoryBarChart
            datos={interanualGrafico}
            categoria="anio"
            series={[{ key: "pct", label: "% conciliado" }]}
            formatoValor={(v) => `${v.toFixed(1)}%`}
            alto={220}
            vacio="Sin años suficientes para comparar."
          />
        ) : (
          <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
            Comparación interanual no disponible — el rango consultado cubre un solo año.
          </p>
        )}
        <DataTable
          rows={interanual}
          keyField={(a) => a.anio}
          vacio="Sin años consolidados."
          columns={[
            { header: "Año", render: (a) => a.anio },
            { header: "% conciliado", render: (a) => pct(a.pct_conciliado) },
            { header: "Registros", render: (a) => entero(a.total_registros) },
          ]}
        />
        {datasetMixto && (
          <NotaLimitacion>
            <strong>Dataset mixto:</strong> el rango incluye más de un año y en este entorno eso mezcla el
            dataset histórico de calibración (NYC 2021, ~1,3 M de viajes sembrados) con la operación real
            de demo (2026). La comparación interanual no es homogénea — no leerla como evolución del
            negocio.
          </NotaLimitacion>
        )}
      </Card>
    </div>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
      <h2 style={{ margin: 0 }}>Panel de Integridad Financiera</h2>
      {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
      <DashboardZ kpis={kpis} grafico={grafico} lista={lista} />
    </div>
  );
}
