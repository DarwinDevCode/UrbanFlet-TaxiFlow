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
import { FilaFiltros, TituloTarjeta } from "./comunes";
import { entero, OPCIONES_VENTANA, pct, tonoVariacion, variacion } from "./formato";

// spec: specs/nivel-estrategico/nivel_estrategico.md §3.6.a — Panel de
// Cumplimiento Normativo (OE6a). Patrón Z.
const RECURSO = "/cumplimiento/panel-estrategico/cumplimiento-normativo";

const SIN_TENDENCIA: PuntoVigencia[] = [];
const SIN_TIPOS: TipoDocumentoVigencia[] = [];

interface PuntoVigencia {
  periodo: string;
  pct_vigente: number;
  total_registros: number;
  documentos_vencidos: number;
}

interface TipoDocumentoVigencia {
  tipo: string;
  pct_vigente: number;
  total_registros: number;
  documentos_vencidos: number;
}

interface PanelCumplimientoNormativoOut {
  kpis: {
    pct_vigente: number | null;
    variacion_vigencia_pct: number | null;
    documentos_vencidos: number;
    tipo_mas_expuesto: string | null;
  };
  tendencia_vigencia: PuntoVigencia[];
  tipos: TipoDocumentoVigencia[];
  metadata: { cortes: number; fuentes: string[] };
}

export function PanelCumplimientoNormativo() {
  const [cortes, setCortes] = useState("12");
  const [filtroTipo, setFiltroTipo] = useState("");

  const clave = `${RECURSO}?cortes=${cortes}`;
  const { data, error: errorCarga } = useSwr<PanelCumplimientoNormativoOut>(clave, () =>
    apiFetch<PanelCumplimientoNormativoOut>(clave),
  );
  const error = errorCarga
    ? errorCarga instanceof ApiError
      ? errorCarga.message
      : "No se pudo cargar el panel de cumplimiento normativo"
    : null;

  const k = data?.kpis;
  const tendencia = data?.tendencia_vigencia ?? SIN_TENDENCIA;
  const tipos = data?.tipos ?? SIN_TIPOS;

  const serieVigencia = useMemo(
    () => tendencia.map((p) => ({ periodo: p.periodo, pct: p.pct_vigente * 100 })),
    [tendencia],
  );
  const tiposGrafico = useMemo(
    () => tipos.map((t) => ({ tipo: t.tipo.replace(/_/g, " "), pct: t.pct_vigente * 100 })),
    [tipos],
  );
  const tiposFiltrados = useMemo(
    () => (filtroTipo ? tipos.filter((t) => t.tipo === filtroTipo) : tipos),
    [tipos, filtroTipo],
  );

  const kpis = (
    <KpiRow>
      <KpiCard
        etiqueta="Documentación vigente"
        valor={pct(k?.pct_vigente)}
        tono={k?.pct_vigente != null && k.pct_vigente < 0.9 ? "peligro" : "exito"}
      />
      <KpiCard
        etiqueta="Variación de vigencia"
        valor={variacion(k?.variacion_vigencia_pct)}
        tono={tonoVariacion(k?.variacion_vigencia_pct, { subirEsBueno: true })}
      />
      <KpiCard
        etiqueta="Documentos vencidos"
        valor={entero(k?.documentos_vencidos)}
        tono={(k?.documentos_vencidos ?? 0) > 0 ? "peligro" : undefined}
      />
      <KpiCard etiqueta="Tipo más expuesto" valor={k?.tipo_mas_expuesto?.replace(/_/g, " ") ?? "—"} />
    </KpiRow>
  );

  const grafico = (
    <Card>
      <TituloTarjeta titulo="Tendencia de vigencia documental" extra={<FuenteBadge tipo="compuesto" />} />
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
        datos={serieVigencia}
        eje="periodo"
        series={[{ key: "pct", label: "% vigente" }]}
        formatoValor={(v) => `${v.toFixed(1)}%`}
        vacio="Sin cortes publicados todavía de vigencia documental."
      />
      <TituloTarjeta titulo="Vigencia por tipo de documento" />
      <CategoryBarChart
        datos={tiposGrafico}
        categoria="tipo"
        series={[{ key: "pct", label: "% vigente" }]}
        formatoValor={(v) => `${v.toFixed(1)}%`}
        alto={240}
        vacio="Sin tipos de documento publicados en el último corte."
      />
    </Card>
  );

  const lista = (
    <Card>
      <TituloTarjeta titulo="Exposición por tipo de documento" extra={<FuenteBadge tipo="compuesto" />} />
      <FilaFiltros>
        <div style={{ minWidth: 240 }}>
          <Select
            label="Tipo de documento"
            value={filtroTipo}
            onChange={(e) => setFiltroTipo(e.target.value)}
            options={[
              { value: "", label: "Todos" },
              ...tipos.map((t) => ({ value: t.tipo, label: t.tipo.replace(/_/g, " ") })),
            ]}
          />
        </div>
      </FilaFiltros>
      <DataTable
        rows={tiposFiltrados}
        keyField={(t) => t.tipo}
        vacio="Sin tipos de documento con este filtro."
        columns={[
          { header: "Tipo", render: (t) => t.tipo.replace(/_/g, " ") },
          {
            header: "% vigente",
            render: (t) => (
              <Badge
                texto={pct(t.pct_vigente)}
                tono={t.pct_vigente >= 0.9 ? "exito" : t.pct_vigente >= 0.7 ? "advertencia" : "peligro"}
              />
            ),
          },
          { header: "Vencidos", render: (t) => entero(t.documentos_vencidos) },
          { header: "Total", render: (t) => entero(t.total_registros) },
        ]}
      />
    </Card>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
      <h2 style={{ margin: 0 }}>Panel de Cumplimiento Normativo</h2>
      {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
      <DashboardZ kpis={kpis} grafico={grafico} lista={lista} />
    </div>
  );
}
