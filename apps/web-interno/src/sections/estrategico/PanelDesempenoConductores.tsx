import {
  ApiError,
  apiFetch,
  BulletBarChart,
  Card,
  DashboardZ,
  DataTable,
  FuenteBadge,
  KpiCard,
  KpiRow,
  Select,
  useSwr,
} from "@urbanflet/shared-ui";
import { useMemo, useState } from "react";
import { FilaFiltros, NotaLimitacion, TituloTarjeta } from "./comunes";
import { entero, moneda, pct } from "./formato";

// Panel estratégico "Desempeño de Conductores" (gerencia, coordinador_operaciones)
// sobre `GET /viajes/panel-estrategico/desempeno-conductores` -- segunda capa
// de agregación por socio × TRIMESTRE. Reconstruido (noviembre 2026) tras la
// pérdida del archivo original, que nunca llegó a commitearse.

interface FilaTrimestral {
  conductor_id: string;
  conductor_nombre: string | null;
  trimestre: string;
  viajes_completados: number;
  viajes_cancelados: number;
  pct_exito: number | null;
  calificacion_promedio: number | null;
  bruto: number | null;
  comisiones: number | null;
  neto: number | null;
}

interface PanelTrimestral {
  filas: FilaTrimestral[];
  metadata: { advertencia_concentracion_historica?: boolean };
}

const SIN_FILAS: FilaTrimestral[] = [];

export function PanelDesempenoConductores() {
  const [trimestres, setTrimestres] = useState("4");
  const [trimestre, setTrimestre] = useState("");

  const url = `/viajes/panel-estrategico/desempeno-conductores?trimestres=${trimestres}`;
  const { data, error } = useSwr(url, () => apiFetch<PanelTrimestral>(url));
  const filas = data?.filas ?? SIN_FILAS;

  const opcionesTrimestre = useMemo(() => [...new Set(filas.map((f) => f.trimestre))].sort(), [filas]);
  const filtradas = useMemo(() => (trimestre ? filas.filter((f) => f.trimestre === trimestre) : filas), [filas, trimestre]);

  const ranking = useMemo(() => {
    const acc = new Map<string, { socio: string; viajes: number }>();
    for (const f of filtradas) {
      const prev = acc.get(f.conductor_id) ?? { socio: f.conductor_nombre ?? f.conductor_id.slice(0, 8), viajes: 0 };
      prev.viajes += f.viajes_completados;
      acc.set(f.conductor_id, prev);
    }
    return [...acc.values()].sort((a, b) => b.viajes - a.viajes).slice(0, 10);
  }, [filtradas]);

  const completados = filtradas.reduce((s, f) => s + f.viajes_completados, 0);
  const cancelados = filtradas.reduce((s, f) => s + f.viajes_cancelados, 0);
  const neto = filtradas.reduce((s, f) => s + (f.neto ?? 0), 0);

  const kpis = (
    <KpiRow>
      <KpiCard etiqueta="Socios" valor={entero(new Set(filtradas.map((f) => f.conductor_id)).size)} />
      <KpiCard etiqueta="Viajes completados" valor={entero(completados)} />
      <KpiCard etiqueta="% de éxito" valor={pct(completados + cancelados ? completados / (completados + cancelados) : null)} />
      <KpiCard etiqueta="Ingreso neto de socios" valor={moneda(neto)} />
    </KpiRow>
  );

  const grafico = (
    <Card>
      <TituloTarjeta titulo="Top 10 socios por viajes completados" extra={<FuenteBadge tipo="compuesto" />} />
      <FilaFiltros>
        <div style={{ minWidth: 160 }}>
          <Select
            label="Ventana"
            value={trimestres}
            onChange={(e) => setTrimestres(e.target.value)}
            options={[
              { value: "2", label: "Últimos 2 trimestres" },
              { value: "4", label: "Últimos 4 trimestres" },
              { value: "8", label: "Últimos 8 trimestres" },
            ]}
          />
        </div>
        <div style={{ minWidth: 160 }}>
          <Select
            label="Trimestre"
            value={trimestre}
            onChange={(e) => setTrimestre(e.target.value)}
            options={[{ value: "", label: "Todos" }, ...opcionesTrimestre.map((t) => ({ value: t, label: t }))]}
          />
        </div>
      </FilaFiltros>
      {error ? <p style={{ color: "var(--color-danger)" }}>{error instanceof ApiError ? error.message : "No se pudo cargar el panel"}</p> : null}
      <BulletBarChart datos={ranking} categoria="socio" valor="viajes" etiquetaValor="Viajes completados" formatoValor={(v) => entero(v)} />
      {data?.metadata.advertencia_concentracion_historica && (
        <NotaLimitacion>El resultado incluye datos históricos de calibración concentrados en pocos socios.</NotaLimitacion>
      )}
    </Card>
  );

  const lista = (
    <Card>
      <TituloTarjeta titulo="Detalle por socio y trimestre" extra={<FuenteBadge tipo="compuesto" />} />
      <DataTable
        rows={filtradas}
        keyField={(f) => `${f.conductor_id}-${f.trimestre}`}
        altoMaximo={620}
        vacio="Sin datos publicados para la ventana consultada."
        columns={[
          { header: "Socio", render: (f) => f.conductor_nombre ?? f.conductor_id.slice(0, 8) },
          { header: "Trimestre", render: (f) => f.trimestre },
          { header: "Completados", render: (f) => entero(f.viajes_completados), numerica: true },
          { header: "% éxito", render: (f) => pct(f.pct_exito), numerica: true },
          {
            header: "Calificación",
            render: (f) => (f.calificacion_promedio != null ? `${f.calificacion_promedio.toFixed(1)}★` : "—"),
            numerica: true,
            prioridad: "media",
          },
          { header: "Neto", render: (f) => moneda(f.neto), numerica: true, prioridad: "baja" },
        ]}
      />
    </Card>
  );

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Panel de Desempeño de Conductores</h2>
      <DashboardZ kpis={kpis} grafico={grafico} lista={lista} />
    </div>
  );
}
