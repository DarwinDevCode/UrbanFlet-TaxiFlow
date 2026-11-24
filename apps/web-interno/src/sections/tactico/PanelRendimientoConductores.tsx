import {
  ApiError,
  apiFetch,
  BulletBarChart,
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
import { entero, moneda, pct } from "../estrategico/formato";

// Panel táctico "Rendimiento de Conductores" (coordinador_operaciones) sobre
// `GET /viajes/panel-tactico/desempeno-conductores` -- combina
// rpt_desempeno_conductor + rpt_ingreso_conductor por socio y mes. Toda la
// agregación ya viene del backend; acá solo se filtra y presenta.
// Reconstruido (noviembre 2026) tras la pérdida del archivo original, que
// nunca llegó a commitearse.

interface FilaDesempeno {
  conductor_id: string;
  conductor_nombre: string | null;
  periodo: string;
  viajes_completados: number;
  viajes_cancelados: number;
  pct_exito: number;
  calificacion_promedio: number | null;
  bruto: number | null;
  comisiones: number | null;
  neto: number | null;
  sin_actividad: boolean;
}

interface PanelDesempeno {
  filas: FilaDesempeno[];
  km_por_socio: { conductor_id: string; conductor_nombre: string | null; km_total: number }[];
  histograma_calificaciones: { estrellas: number; viajes: number }[];
  metadata: { advertencia_concentracion_historica?: boolean };
}

const SIN_FILAS: FilaDesempeno[] = [];

export function PanelRendimientoConductores() {
  const [meses, setMeses] = useState("3");
  const [historico, setHistorico] = useState(false);
  const [busqueda, setBusqueda] = useState("");

  const url = `/viajes/panel-tactico/desempeno-conductores?meses=${meses}&historico_completo=${historico}`;
  const { data, error } = useSwr(url, () => apiFetch<PanelDesempeno>(url));
  const filas = data?.filas ?? SIN_FILAS;

  const filtradas = useMemo(() => {
    const q = busqueda.trim().toLowerCase();
    return q ? filas.filter((f) => (f.conductor_nombre ?? "").toLowerCase().includes(q)) : filas;
  }, [filas, busqueda]);

  // Totales por socio (suma de la ventana) para el ranking.
  const ranking = useMemo(() => {
    const acc = new Map<string, { socio: string; viajes: number }>();
    for (const f of filtradas) {
      const k = f.conductor_id;
      const prev = acc.get(k) ?? { socio: f.conductor_nombre ?? k.slice(0, 8), viajes: 0 };
      prev.viajes += f.viajes_completados;
      acc.set(k, prev);
    }
    return [...acc.values()].sort((a, b) => b.viajes - a.viajes).slice(0, 10);
  }, [filtradas]);

  const socios = new Set(filtradas.map((f) => f.conductor_id)).size;
  const completados = filtradas.reduce((s, f) => s + f.viajes_completados, 0);
  const cancelados = filtradas.reduce((s, f) => s + f.viajes_cancelados, 0);
  const calificadas = filtradas.filter((f) => f.calificacion_promedio != null);
  const calificacion = calificadas.length
    ? calificadas.reduce((s, f) => s + (f.calificacion_promedio ?? 0), 0) / calificadas.length
    : null;

  const kpis = (
    <KpiRow>
      <KpiCard etiqueta="Socios en la ventana" valor={entero(socios)} descripcion="Conductores con actividad en el periodo." />
      <KpiCard etiqueta="Viajes completados" valor={entero(completados)} />
      <KpiCard
        etiqueta="% de éxito"
        valor={pct(completados + cancelados ? completados / (completados + cancelados) : null)}
        descripcion="Completados sobre completados + cancelados."
      />
      <KpiCard etiqueta="Calificación promedio" valor={calificacion != null ? `${calificacion.toFixed(2)}★` : "—"} />
    </KpiRow>
  );

  const grafico = (
    <Card>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-3)" }}>
        <h3 style={{ margin: 0, fontSize: "var(--font-size-md)" }}>Viajes completados por socio (top 10)</h3>
        <FuenteBadge tipo="compuesto" />
      </div>
      <div style={{ display: "flex", gap: "var(--space-3)", flexWrap: "wrap", marginBottom: "var(--space-3)" }}>
        <div style={{ minWidth: 160 }}>
          <Select
            label="Ventana"
            value={meses}
            onChange={(e) => setMeses(e.target.value)}
            options={[
              { value: "1", label: "Último mes" },
              { value: "3", label: "Últimos 3 meses" },
              { value: "6", label: "Últimos 6 meses" },
              { value: "12", label: "Últimos 12 meses" },
            ]}
          />
        </div>
        <div style={{ minWidth: 160 }}>
          <Select
            label="Alcance"
            value={historico ? "1" : "0"}
            onChange={(e) => setHistorico(e.target.value === "1")}
            options={[
              { value: "0", label: "Ventana reciente" },
              { value: "1", label: "Histórico completo" },
            ]}
          />
        </div>
        <div style={{ minWidth: 200 }}>
          <TextField label="Buscar socio" value={busqueda} onChange={(e) => setBusqueda(e.target.value)} />
        </div>
      </div>
      {error ? <p style={{ color: "var(--color-danger)" }}>{error instanceof ApiError ? error.message : "No se pudo cargar el panel"}</p> : null}
      {data?.metadata.advertencia_concentracion_historica && (
        <p style={{ marginTop: 0, fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>
          El resultado incluye datos históricos de calibración concentrados en pocos socios.
        </p>
      )}
      <BulletBarChart datos={ranking} categoria="socio" valor="viajes" etiquetaValor="Viajes completados" formatoValor={(v) => entero(v)} />
      <h3 style={{ margin: "var(--space-4) 0 var(--space-2)", fontSize: "var(--font-size-md)" }}>Distribución de calificaciones</h3>
      <CategoryBarChart
        datos={(data?.histograma_calificaciones ?? []).map((h) => ({ estrellas: `${h.estrellas}★`, viajes: h.viajes }))}
        categoria="estrellas"
        series={[{ key: "viajes", label: "Viajes" }]}
        alto={180}
        vacio="Sin calificaciones en la ventana."
      />
    </Card>
  );

  const lista = (
    <Card>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-3)" }}>
        <h3 style={{ margin: 0, fontSize: "var(--font-size-md)" }}>Detalle por socio y mes</h3>
        <FuenteBadge tipo="compuesto" />
      </div>
      <DataTable
        rows={filtradas}
        keyField={(f) => `${f.conductor_id}-${f.periodo}`}
        altoMaximo={620}
        vacio="Sin actividad de conductores en la ventana consultada."
        columns={[
          { header: "Socio", render: (f) => f.conductor_nombre ?? f.conductor_id.slice(0, 8) },
          { header: "Periodo", render: (f) => f.periodo },
          { header: "Completados", render: (f) => entero(f.viajes_completados), numerica: true },
          { header: "Cancelados", render: (f) => entero(f.viajes_cancelados), numerica: true, prioridad: "media" },
          { header: "% éxito", render: (f) => pct(f.pct_exito), numerica: true },
          {
            header: "Calificación",
            render: (f) => (f.calificacion_promedio != null ? `${f.calificacion_promedio.toFixed(1)}★` : "—"),
            numerica: true,
          },
          { header: "Neto", render: (f) => moneda(f.neto), numerica: true, prioridad: "baja" },
        ]}
      />
    </Card>
  );

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Panel de Rendimiento de Conductores</h2>
      <DashboardZ kpis={kpis} grafico={grafico} lista={lista} />
    </div>
  );
}
