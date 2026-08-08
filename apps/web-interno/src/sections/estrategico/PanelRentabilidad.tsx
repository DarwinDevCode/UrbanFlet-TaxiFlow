import {
  ApiError,
  apiFetch,
  Badge,
  Card,
  DashboardF,
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
import { moneda, OPCIONES_VENTANA, pct, tonoVariacion, variacion } from "./formato";

// spec: specs/nivel-estrategico/nivel_estrategico.md §3.4 — Panel de
// Rentabilidad y Demanda (OE4 / CU-E02 + CU-E03). **Patrón F**, uno de los 2
// de los 9: es herramienta de análisis comparativo, no tablero de estado —
// la matriz de margen es el elemento dominante y los KPIs son una franja
// delgada de contexto arriba.
const RECURSO = "/estrategico/rentabilidad-demanda";

const SIN_MATRIZ: CeldaRentabilidad[] = [];
const SIN_RESUMEN: ResumenFranja[] = [];
const SIN_DEMANDA: PuntoDemanda[] = [];

interface CeldaRentabilidad {
  periodo: string;
  franja: string;
  recaudacion: number;
  comision: number;
  costo_mantenimiento: number;
  margen: number;
  margen_pct: number | null;
  share_demanda: number;
  share_capacidad: number;
}

interface ResumenFranja {
  franja: string;
  recaudacion: number;
  comision: number;
  costo_mantenimiento: number;
  margen: number;
  margen_pct: number | null;
}

interface PuntoDemanda {
  periodo: string;
  recaudacion: number;
  meses: number;
}

interface PanelRentabilidadOut {
  kpis: {
    margen_promedio_pct: number | null;
    franja_menos_rentable: string | null;
    margen_menos_rentable_pct: number | null;
    recaudacion_ultimo_trimestre: number | null;
    variacion_recaudacion_trimestral_pct: number | null;
  };
  matriz: CeldaRentabilidad[];
  resumen_franja: ResumenFranja[];
  tendencia_demanda: PuntoDemanda[];
  metadata: {
    meses: number;
    zona_disponible: boolean;
    demanda_viajes_disponible: boolean;
    formula: string;
    fuentes: string[];
  };
}

function tonoMargen(margenPct: number | null): "exito" | "advertencia" | "peligro" {
  if (margenPct == null) return "advertencia";
  if (margenPct >= 0.3) return "exito";
  if (margenPct >= 0) return "advertencia";
  return "peligro";
}

export function PanelRentabilidad() {
  const [meses, setMeses] = useState("12");
  const [filtroFranja, setFiltroFranja] = useState("");

  const clave = `${RECURSO}?meses=${meses}`;
  const { data, error: errorCarga } = useSwr<PanelRentabilidadOut>(clave, () =>
    apiFetch<PanelRentabilidadOut>(clave),
  );
  const error = errorCarga
    ? errorCarga instanceof ApiError
      ? errorCarga.message
      : "No se pudo cargar el panel de rentabilidad"
    : null;

  const k = data?.kpis;
  const matriz = data?.matriz ?? SIN_MATRIZ;
  const resumenFranja = data?.resumen_franja ?? SIN_RESUMEN;
  const tendenciaDemanda = data?.tendencia_demanda ?? SIN_DEMANDA;
  const zonaDisponible = data?.metadata.zona_disponible ?? false;
  const demandaViajesDisponible = data?.metadata.demanda_viajes_disponible ?? false;
  const formula = data?.metadata.formula;

  const franjas = useMemo(() => Array.from(new Set(matriz.map((c) => c.franja))).sort(), [matriz]);
  const matrizFiltrada = useMemo(
    () => (filtroFranja ? matriz.filter((c) => c.franja === filtroFranja) : matriz),
    [matriz, filtroFranja],
  );

  const kpis = (
    <>
      <KpiRow>
        <KpiCard etiqueta="Margen promedio" valor={pct(k?.margen_promedio_pct)} />
        <KpiCard etiqueta="Franja menos rentable" valor={k?.franja_menos_rentable ?? "—"} />
        <KpiCard
          etiqueta="Margen de esa franja"
          valor={pct(k?.margen_menos_rentable_pct)}
          tono={tonoMargen(k?.margen_menos_rentable_pct ?? null)}
        />
        <KpiCard etiqueta="Recaudación último trimestre" valor={moneda(k?.recaudacion_ultimo_trimestre)} />
        <KpiCard
          etiqueta="Variación trimestral"
          valor={variacion(k?.variacion_recaudacion_trimestral_pct)}
          tono={tonoVariacion(k?.variacion_recaudacion_trimestral_pct, { subirEsBueno: true })}
        />
      </KpiRow>
      {!zonaDisponible && (
        <NotaLimitacion>
          Dimensión <strong>zona</strong> no disponible: <code>viajes.zona_origen_id</code> nunca se
          resuelve en la operación, así que la matriz que la spec pide como zona × franja se construye
          como <strong>mes × franja</strong>. La decisión de "dónde reforzar flota" queda sin soporte de
          datos; la de "cuándo" sí.
        </NotaLimitacion>
      )}
    </>
  );

  const grafico = (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
      <Card>
        <TituloTarjeta titulo="Demanda de largo plazo" extra={<FuenteBadge tipo="compuesto" />} />
        <FilaFiltros>
          <div style={{ minWidth: 160 }}>
            <Select
              label="Ventana (meses)"
              value={meses}
              onChange={(e) => setMeses(e.target.value)}
              options={OPCIONES_VENTANA}
            />
          </div>
        </FilaFiltros>
        <TrendLineChart
          datos={tendenciaDemanda}
          eje="periodo"
          series={[{ key: "recaudacion", label: "Recaudación" }]}
          formatoValor={(v) => moneda(v, 0)}
          alto={220}
          vacio="Sin trimestres publicados todavía."
        />
        {!demandaViajesDisponible && (
          <NotaLimitacion>
            La demanda de largo plazo se expresa como <strong>recaudación bruta por trimestre</strong>:
            ninguna vista <code>rpt_*</code> publica el conteo de viajes solicitados por mes.
          </NotaLimitacion>
        )}
      </Card>

      <Card>
        <TituloTarjeta titulo="Resumen por franja" extra={<FuenteBadge tipo="compuesto" />} />
        <DataTable
          rows={resumenFranja}
          keyField={(f) => f.franja}
          vacio="Sin datos consolidados por franja."
          columns={[
            { header: "Franja", render: (f) => f.franja },
            { header: "Margen", render: (f) => moneda(f.margen) },
            {
              header: "Margen %",
              render: (f) => <Badge texto={pct(f.margen_pct)} tono={tonoMargen(f.margen_pct)} />,
            },
          ]}
        />
      </Card>
    </div>
  );

  const lista = (
    <Card>
      <TituloTarjeta titulo="Matriz de rentabilidad — mes × franja" extra={<FuenteBadge tipo="compuesto" />} />
      <FilaFiltros>
        <div style={{ minWidth: 180 }}>
          <Select
            label="Franja"
            value={filtroFranja}
            onChange={(e) => setFiltroFranja(e.target.value)}
            options={[{ value: "", label: "Todas" }, ...franjas.map((f) => ({ value: f, label: f }))]}
          />
        </div>
        <div style={{ minWidth: 180 }}>
          <Select label="Zona" value="" onChange={() => undefined} disabled options={[{ value: "", label: "No disponible" }]} />
        </div>
      </FilaFiltros>
      <DataTable
        rows={matrizFiltrada}
        keyField={(c) => `${c.periodo}|${c.franja}`}
        vacio="Sin celdas de rentabilidad para esta ventana."
        altoMaximo={520}
        columns={[
          { header: "Periodo", render: (c) => c.periodo },
          { header: "Franja", render: (c) => c.franja },
          { header: "Recaudación", render: (c) => moneda(c.recaudacion) },
          { header: "Comisión", render: (c) => moneda(c.comision) },
          { header: "Costo mant.", render: (c) => moneda(c.costo_mantenimiento) },
          { header: "Margen", render: (c) => moneda(c.margen) },
          {
            header: "Margen %",
            render: (c) => <Badge texto={pct(c.margen_pct)} tono={tonoMargen(c.margen_pct)} />,
          },
          { header: "Share demanda", render: (c) => pct(c.share_demanda) },
          { header: "Share capacidad", render: (c) => pct(c.share_capacidad) },
        ]}
      />
      {formula && (
        <NotaLimitacion>
          <strong>Fórmula aplicada:</strong> {formula} La recaudación y la comisión se prorratean por
          participación en la <em>demanda atendida</em>; el costo de mantenimiento, por{" "}
          <em>capacidad expuesta</em> — un vehículo en servicio se desgasta esté ocupado o no.
        </NotaLimitacion>
      )}
    </Card>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <h2 style={{ margin: 0 }}>Panel de Rentabilidad y Demanda</h2>
      {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
      <DashboardF kpis={kpis} grafico={grafico} lista={lista} />
    </div>
  );
}
