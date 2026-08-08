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

// spec: specs/nivel-estrategico/nivel_estrategico.md §3.3 — Panel de
// Capacidades y Plataforma (OE3). Patrón Z.
const RECURSO = "/plataforma/panel-estrategico/capacidades";

const SIN_TENDENCIA: PuntoCuarentena[] = [];
const SIN_DOMINIOS: DominioCuarentena[] = [];

interface PuntoCuarentena {
  periodo: string;
  pct_cuarentena: number;
  registros_extraidos: number;
  registros_cuarentena: number;
}

interface DominioCuarentena {
  dag_id: string;
  pct_cuarentena: number;
  registros_extraidos: number;
  registros_cuarentena: number;
}

interface PanelCapacidadesOut {
  kpis: {
    pct_cuarentena_global: number | null;
    variacion_cuarentena_pct: number | null;
    dominio_mas_afectado: string | null;
    corridas_ok: number;
    corridas_fallidas: number;
    avance_capacitacion_pct: number | null;
  };
  tendencia_cuarentena: PuntoCuarentena[];
  dominios: DominioCuarentena[];
  metadata: { cortes: number; capacitacion_disponible: boolean; fuentes: string[] };
}

export function PanelCapacidades() {
  const [cortes, setCortes] = useState("12");
  const [filtroDominio, setFiltroDominio] = useState("");

  const clave = `${RECURSO}?cortes=${cortes}`;
  const { data, error: errorCarga } = useSwr<PanelCapacidadesOut>(clave, () =>
    apiFetch<PanelCapacidadesOut>(clave),
  );
  const error = errorCarga
    ? errorCarga instanceof ApiError
      ? errorCarga.message
      : "No se pudo cargar el panel de capacidades"
    : null;

  const k = data?.kpis;
  const tendencia = data?.tendencia_cuarentena ?? SIN_TENDENCIA;
  const dominios = data?.dominios ?? SIN_DOMINIOS;
  const capacitacionDisponible = data?.metadata.capacitacion_disponible ?? false;

  const serieTendencia = useMemo(
    () => tendencia.map((p) => ({ periodo: p.periodo, pct: p.pct_cuarentena * 100 })),
    [tendencia],
  );
  const dominiosGrafico = useMemo(
    () => dominios.map((d) => ({ dag_id: d.dag_id.replace(/^dag_/, ""), pct: d.pct_cuarentena * 100 })),
    [dominios],
  );
  const dominiosFiltrados = useMemo(
    () => (filtroDominio ? dominios.filter((d) => d.dag_id === filtroDominio) : dominios),
    [dominios, filtroDominio],
  );

  const kpis = (
    <>
      <KpiRow>
        <KpiCard
          etiqueta="Cuarentena global"
          valor={pct(k?.pct_cuarentena_global, 2)}
          tono={k?.pct_cuarentena_global != null && k.pct_cuarentena_global > 0.05 ? "advertencia" : undefined}
        />
        <KpiCard
          etiqueta="Variación de cuarentena"
          valor={variacion(k?.variacion_cuarentena_pct)}
          tono={tonoVariacion(k?.variacion_cuarentena_pct, { subirEsBueno: false })}
        />
        <KpiCard etiqueta="Dominio más afectado" valor={k?.dominio_mas_afectado?.replace(/^dag_/, "") ?? "—"} />
        <KpiCard etiqueta="Corridas OK" valor={entero(k?.corridas_ok)} />
        <KpiCard
          etiqueta="Corridas fallidas"
          valor={entero(k?.corridas_fallidas)}
          tono={(k?.corridas_fallidas ?? 0) > 0 ? "peligro" : undefined}
        />
        <KpiCard etiqueta="Avance de capacitación" valor={pct(k?.avance_capacitacion_pct)} />
      </KpiRow>
      {!capacitacionDisponible && (
        <NotaLimitacion>
          "Avance de capacitación" no disponible — no existe ningún dominio de capacitación en el
          sistema (backlog consciente ya declarado en el nivel táctico). Se muestra "—" en vez de un
          valor inventado.
        </NotaLimitacion>
      )}
    </>
  );

  const grafico = (
    <Card>
      <TituloTarjeta titulo="Tendencia de % de cuarentena" extra={<FuenteBadge tipo="compuesto" />} />
      <FilaFiltros>
        <div style={{ minWidth: 180 }}>
          <Select
            label="Ventana (cortes)"
            value={cortes}
            onChange={(e) => setCortes(e.target.value)}
            options={OPCIONES_VENTANA}
          />
        </div>
      </FilaFiltros>
      <TrendLineChart
        datos={serieTendencia}
        eje="periodo"
        series={[{ key: "pct", label: "% cuarentena" }]}
        formatoValor={(v) => `${v.toFixed(2)}%`}
        vacio="Sin cortes publicados todavía de calidad del pipeline."
      />
      <TituloTarjeta titulo="Cuarentena por dominio (último corte)" />
      <CategoryBarChart
        datos={dominiosGrafico}
        categoria="dag_id"
        series={[{ key: "pct", label: "% cuarentena" }]}
        formatoValor={(v) => `${v.toFixed(2)}%`}
        alto={240}
        vacio="Sin dominios publicados en el último corte."
      />
    </Card>
  );

  const lista = (
    <Card>
      <TituloTarjeta titulo="Calidad de datos por dominio" extra={<FuenteBadge tipo="compuesto" />} />
      <FilaFiltros>
        <div style={{ minWidth: 220 }}>
          <Select
            label="Dominio"
            value={filtroDominio}
            onChange={(e) => setFiltroDominio(e.target.value)}
            options={[
              { value: "", label: "Todos" },
              ...dominios.map((d) => ({ value: d.dag_id, label: d.dag_id })),
            ]}
          />
        </div>
      </FilaFiltros>
      <DataTable
        rows={dominiosFiltrados}
        keyField={(d) => d.dag_id}
        vacio="Sin dominios con corridas registradas."
        columns={[
          { header: "Dominio (DAG)", render: (d) => d.dag_id },
          {
            header: "% cuarentena",
            render: (d) => (
              <Badge
                texto={pct(d.pct_cuarentena, 2)}
                tono={d.pct_cuarentena === 0 ? "exito" : d.pct_cuarentena < 0.05 ? "advertencia" : "peligro"}
              />
            ),
          },
          { header: "Extraídos", render: (d) => entero(d.registros_extraidos) },
          { header: "En cuarentena", render: (d) => entero(d.registros_cuarentena) },
        ]}
      />
    </Card>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
      <h2 style={{ margin: 0 }}>Panel de Capacidades y Plataforma</h2>
      {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
      <DashboardZ kpis={kpis} grafico={grafico} lista={lista} />
    </div>
  );
}
