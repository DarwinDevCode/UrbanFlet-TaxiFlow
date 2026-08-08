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
  useSwr,
} from "@urbanflet/shared-ui";
import { useMemo, useState } from "react";

const RECURSO_PANEL_PLATAFORMA = "/plataforma/panel-tactico";

// Ver PanelMantenimiento.tsx: referencia estable para el fallback de
// `data?.campo ?? []`, evita invalidar los `useMemo` que dependen de esto.
const SIN_CORRIDAS: Corrida[] = [];
const SIN_CUARENTENA: CuarentenaDominio[] = [];

interface Corrida {
  dag_id: string;
  fecha_logica: string;
  estado: string;
  registros_extraidos: number;
  registros_cuarentena: number;
  pct_cuarentena: number;
  iniciado_en: string;
  finalizado_en: string | null;
}

interface CuarentenaDominio {
  dag_id: string;
  pct_cuarentena: number;
  registros_extraidos: number;
  registros_cuarentena: number;
}

// spec: specs/nivel-tactico/tactico_plataforma.md — Panel de Salud del
// Pipeline y Capacitación (CU-T14/T15). Patrón Z. "Avance de capacitación
// por área" es backlog consciente — no existe dominio de capacitación en el
// sistema.
interface DatosPanelPlataforma {
  corridas: Corrida[];
  cuarentena: CuarentenaDominio[];
}

export function PanelPlataforma() {
  const [filtroDominio, setFiltroDominio] = useState("");
  const [filtroFechaLogica, setFiltroFechaLogica] = useState("");

  const claveConsulta = `${RECURSO_PANEL_PLATAFORMA}?dominio=${filtroDominio}&fecha_logica=${filtroFechaLogica}`;
  const { data, error: errorCarga } = useSwr<DatosPanelPlataforma>(claveConsulta, async () => {
    const params = new URLSearchParams();
    if (filtroDominio) params.set("dominio", filtroDominio);
    if (filtroFechaLogica) params.set("fecha_logica", filtroFechaLogica);
    const [c, cd] = await Promise.all([
      apiFetch<Corrida[]>(`/plataforma/panel-tactico/corridas?${params.toString()}`),
      apiFetch<CuarentenaDominio[]>("/plataforma/panel-tactico/cuarentena-dominio"),
    ]);
    return { corridas: c, cuarentena: cd };
  });
  const corridas = data?.corridas ?? SIN_CORRIDAS;
  const cuarentena = data?.cuarentena ?? SIN_CUARENTENA;
  const error = errorCarga
    ? errorCarga instanceof ApiError
      ? errorCarga.message
      : "No se pudo cargar el panel de plataforma"
    : null;

  const hoy = new Date().toISOString().slice(0, 10);
  const corridasHoyOk = useMemo(
    () => corridas.filter((c) => c.fecha_logica === hoy && (c.estado === "OK" || c.estado === "WARN")).length,
    [corridas, hoy],
  );
  const pctCuarentenaGlobal = cuarentena.length
    ? cuarentena.reduce((acc, c) => acc + c.registros_cuarentena, 0) /
      Math.max(cuarentena.reduce((acc, c) => acc + c.registros_extraidos, 0), 1)
    : null;
  const ultimaCorrida = corridas[0];
  const dominios = Array.from(new Set(corridas.map((c) => c.dag_id))).sort();

  const kpis = (
    <>
      <KpiRow>
        <KpiCard etiqueta="Corridas OK hoy" valor={String(corridasHoyOk)} />
        <KpiCard etiqueta="% cuarentena" valor={pctCuarentenaGlobal != null ? `${(pctCuarentenaGlobal * 100).toFixed(1)}%` : "—"} />
        <KpiCard etiqueta="Última corrida" valor={ultimaCorrida ? new Date(ultimaCorrida.iniciado_en).toLocaleString() : "—"} />
        <KpiCard etiqueta="Capacitación" valor="—" />
      </KpiRow>
      <p style={{ margin: "var(--space-2) 0 0", fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>
        "Capacitación" no disponible — no existe dominio de capacitación en el sistema (backlog consciente).
      </p>
    </>
  );

  const grafico = (
    <Card>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-3)" }}>
        <h3 style={{ margin: 0, fontSize: "var(--font-size-md)" }}>% de cuarentena por dominio</h3>
        <FuenteBadge tipo="compuesto" />
      </div>
      <CategoryBarChart
        datos={cuarentena.map((c) => ({ dominio: c.dag_id.replace("dag_", "").replace("_gold", ""), pct: c.pct_cuarentena * 100 }))}
        categoria="dominio"
        series={[{ key: "pct", label: "% cuarentena" }]}
        formatoValor={(v) => `${v.toFixed(1)}%`}
        vacio="Sin datos publicados todavía de cuarentena por dominio."
      />
    </Card>
  );

  const lista = (
    <Card>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-3)" }}>
        <h3 style={{ margin: 0, fontSize: "var(--font-size-md)" }}>Estado de corridas del pipeline por DAG</h3>
        <FuenteBadge tipo="simple" />
      </div>
      <p style={{ marginTop: 0, fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>
        Servido desde ClickHouse (tabla <code>corridas</code>) — la colección Mongo <code>corridas_etl</code> que
        pide el spec no existe; el seguimiento del pipeline vive en ClickHouse desde el diseño original.
      </p>
      <div style={{ display: "flex", gap: "var(--space-3)", flexWrap: "wrap", marginBottom: "var(--space-4)" }}>
        <div style={{ minWidth: 220 }}>
          <Select
            label="Dominio / DAG"
            value={filtroDominio}
            onChange={(e) => setFiltroDominio(e.target.value)}
            options={[{ value: "", label: "Todos" }, ...dominios.map((d) => ({ value: d, label: d }))]}
          />
        </div>
        <div style={{ minWidth: 160 }}>
          <TextField
            label="Fecha lógica"
            type="date"
            value={filtroFechaLogica}
            onChange={(e) => setFiltroFechaLogica(e.target.value)}
          />
        </div>
      </div>
      <DataTable
        rows={corridas}
        keyField={(c) => `${c.dag_id}-${c.iniciado_en}`}
        vacio="No hay corridas registradas con este filtro."
        columns={[
          { header: "DAG", render: (c) => c.dag_id },
          { header: "Fecha lógica", render: (c) => c.fecha_logica },
          { header: "Estado", render: (c) => <Badge texto={c.estado} tono={c.estado === "FAILED" ? "peligro" : c.estado === "WARN" ? "advertencia" : "exito"} /> },
          { header: "% cuarentena", render: (c) => `${(c.pct_cuarentena * 100).toFixed(1)}%` },
          { header: "Hora", render: (c) => new Date(c.iniciado_en).toLocaleString() },
        ]}
      />
    </Card>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
      <h2 style={{ margin: 0 }}>Panel de Salud del Pipeline y Capacitación</h2>
      {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
      <DashboardZ kpis={kpis} grafico={grafico} lista={lista} />
    </div>
  );
}
