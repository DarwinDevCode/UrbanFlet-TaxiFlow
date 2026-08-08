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
import { entero, OPCIONES_VENTANA, tonoVariacion, variacion } from "./formato";

// spec: specs/nivel-estrategico/nivel_estrategico.md §3.6.b — Panel de
// Gobernanza de Datos y Seguridad (OE6b / CU-E05). **Patrón F**: herramienta
// de investigación, la tabla de eventos domina y los KPIs son franja de
// contexto. Backend gateado en exclusiva a `gerencia` (ni siquiera
// `admin_sistema` lo ve — ya tiene su vista operativa en Administración).
const RECURSO = "/auditoria/panel-estrategico/gobernanza";

const SIN_TENDENCIA: PuntoGobernanza[] = [];
const SIN_EVENTOS: EventoAuditoria[] = [];

interface PuntoGobernanza {
  periodo: string;
  eventos_administrativos: number;
  accesos_denegados: number;
  alertas_seguridad: number;
}

interface EventoAuditoria {
  evento_id: number;
  ts: string;
  actor_id: string | null;
  rol: string | null;
  accion: string;
  entidad: string;
  entidad_id: string | null;
  resultado: string;
}

interface PanelGobernanzaOut {
  kpis: {
    eventos_administrativos: number;
    accesos_denegados: number;
    alertas_seguridad: number;
    variacion_accesos_denegados_pct: number | null;
  };
  tendencia: PuntoGobernanza[];
  eventos: EventoAuditoria[];
  metadata: { meses: number; desde: string; fuente: string };
}

export function PanelGobernanza() {
  const [meses, setMeses] = useState("6");
  const [filtroAccion, setFiltroAccion] = useState("");
  const [filtroResultado, setFiltroResultado] = useState("");

  const clave = `${RECURSO}?meses=${meses}`;
  const { data, error: errorCarga } = useSwr<PanelGobernanzaOut>(clave, () =>
    apiFetch<PanelGobernanzaOut>(clave),
  );
  const error = errorCarga
    ? errorCarga instanceof ApiError
      ? errorCarga.message
      : "No se pudo cargar el panel de gobernanza"
    : null;

  const k = data?.kpis;
  const tendencia = data?.tendencia ?? SIN_TENDENCIA;
  const eventos = data?.eventos ?? SIN_EVENTOS;
  const desde = data?.metadata.desde;

  const acciones = useMemo(
    () => Array.from(new Set(eventos.map((e) => e.accion))).sort(),
    [eventos],
  );
  const eventosFiltrados = useMemo(
    () =>
      eventos.filter((e) => {
        if (filtroAccion && e.accion !== filtroAccion) return false;
        if (filtroResultado && e.resultado !== filtroResultado) return false;
        return true;
      }),
    [eventos, filtroAccion, filtroResultado],
  );

  const kpis = (
    <>
      <KpiRow>
        <KpiCard etiqueta="Eventos administrativos" valor={entero(k?.eventos_administrativos)} />
        <KpiCard
          etiqueta="Accesos denegados"
          valor={entero(k?.accesos_denegados)}
          tono={(k?.accesos_denegados ?? 0) > 0 ? "peligro" : undefined}
        />
        <KpiCard
          etiqueta="Alertas de seguridad"
          valor={entero(k?.alertas_seguridad)}
          tono={(k?.alertas_seguridad ?? 0) > 0 ? "advertencia" : undefined}
        />
        <KpiCard
          etiqueta="Variación de denegaciones"
          valor={variacion(k?.variacion_accesos_denegados_pct)}
          tono={tonoVariacion(k?.variacion_accesos_denegados_pct, { subirEsBueno: false })}
        />
      </KpiRow>
      {desde && (
        <NotaLimitacion>
          Ventana consolidada desde {new Date(desde).toLocaleDateString()}. Fuente: bitácora de auditoría
          (Mongo) — es el único de los 9 dashboards estratégicos sin una vista <code>rpt_*</code> detrás,
          porque los eventos administrativos nunca pasaron por el pipeline Gold.
        </NotaLimitacion>
      )}
    </>
  );

  const grafico = (
    <Card>
      <TituloTarjeta titulo="Tendencia de gobernanza" extra={<FuenteBadge tipo="simple" />} />
      <FilaFiltros>
        <div style={{ minWidth: 150 }}>
          <Select
            label="Ventana (meses)"
            value={meses}
            onChange={(e) => setMeses(e.target.value)}
            options={OPCIONES_VENTANA}
          />
        </div>
      </FilaFiltros>
      <TrendLineChart
        datos={tendencia}
        eje="periodo"
        series={[
          { key: "eventos_administrativos", label: "Administrativos" },
          { key: "accesos_denegados", label: "Denegados" },
          { key: "alertas_seguridad", label: "Alertas" },
        ]}
        formatoValor={(v) => entero(v)}
        alto={420}
        vacio="Sin eventos en la ventana consultada."
      />
    </Card>
  );

  const lista = (
    <Card>
      <TituloTarjeta titulo="Eventos administrativos consolidados" extra={<FuenteBadge tipo="simple" />} />
      <FilaFiltros>
        <div style={{ minWidth: 260 }}>
          <Select
            label="Acción"
            value={filtroAccion}
            onChange={(e) => setFiltroAccion(e.target.value)}
            options={[{ value: "", label: "Todas" }, ...acciones.map((a) => ({ value: a, label: a }))]}
          />
        </div>
        <div style={{ minWidth: 170 }}>
          <Select
            label="Resultado"
            value={filtroResultado}
            onChange={(e) => setFiltroResultado(e.target.value)}
            options={[
              { value: "", label: "Todos" },
              { value: "OK", label: "OK" },
              { value: "DENEGADO", label: "Denegado" },
            ]}
          />
        </div>
      </FilaFiltros>
      <DataTable
        rows={eventosFiltrados}
        keyField={(e) => String(e.evento_id)}
        vacio="No hay eventos administrativos con este filtro."
        altoMaximo={620}
        columns={[
          { header: "Fecha", render: (e) => new Date(e.ts).toLocaleString() },
          { header: "Actor", render: (e) => e.actor_id?.slice(0, 8) + "…" },
          { header: "Rol", width: "160px", render: (e) => e.rol ?? "—" },
          { header: "Acción", render: (e) => e.accion },
          { header: "Entidad", render: (e) => e.entidad },
          {
            header: "Resultado",
            render: (e) => <Badge texto={e.resultado} tono={e.resultado === "DENEGADO" ? "peligro" : "exito"} />,
          },
        ]}
      />
    </Card>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <h2 style={{ margin: 0 }}>Panel de Gobernanza de Datos y Seguridad</h2>
      {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
      <DashboardF kpis={kpis} grafico={grafico} lista={lista} />
    </div>
  );
}
