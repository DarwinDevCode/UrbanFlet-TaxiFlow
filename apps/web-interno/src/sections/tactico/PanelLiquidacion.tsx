import {
  ApiError,
  apiFetch,
  Badge,
  Card,
  DashboardZ,
  DataTable,
  FuenteBadge,
  KpiCard,
  KpiRow,
  Select,
  TextField,
  TrendLineChart,
} from "@urbanflet/shared-ui";
import { useEffect, useMemo, useState } from "react";

interface Liquidacion {
  id: string;
  conductor_nombre: string | null;
  periodo_inicio: string;
  periodo_fin: string;
  estado: string;
  bruto: number;
  comisiones: number;
  neto: number;
}

interface LiquidacionListOut {
  items: Liquidacion[];
  total: number;
}

interface MargenComision {
  periodo: string;
  margen: number;
  bruto_total: number;
  comisiones_total: number;
  horas_hasta_pago_promedio: number | null;
}

// spec: specs/nivel-tactico/tactico_finanzas.md — Panel de Liquidación de Comisiones (CU-T12/OT5.2). Patrón Z.
export function PanelLiquidacion() {
  const [liquidaciones, setLiquidaciones] = useState<Liquidacion[]>([]);
  const [margen, setMargen] = useState<MargenComision[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [filtroEstado, setFiltroEstado] = useState("");
  const [filtroPeriodo, setFiltroPeriodo] = useState("");
  const [filtroSocio, setFiltroSocio] = useState("");

  const cargar = async () => {
    try {
      const [liq, m] = await Promise.all([
        apiFetch<LiquidacionListOut>("/liquidaciones?limit=100"),
        apiFetch<MargenComision[]>("/liquidaciones/panel-tactico/margen-comision"),
      ]);
      setLiquidaciones(liq.items);
      setMargen(m);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo cargar el panel de liquidación");
    }
  };

  useEffect(() => {
    cargar();
  }, []);

  const emitidas = useMemo(() => liquidaciones.filter((l) => l.estado === "EMITIDA"), [liquidaciones]);
  const porAprobar = useMemo(() => liquidaciones.filter((l) => l.estado === "OBSERVADA"), [liquidaciones]);
  const periodosDisponibles = useMemo(
    () => Array.from(new Set(liquidaciones.map((l) => l.periodo_inicio.slice(0, 10)))).sort().reverse(),
    [liquidaciones],
  );
  const liquidacionesFiltradas = useMemo(() => {
    return liquidaciones.filter((l) => {
      if (filtroEstado && l.estado !== filtroEstado) return false;
      if (filtroPeriodo && l.periodo_inicio.slice(0, 10) !== filtroPeriodo) return false;
      if (filtroSocio && !(l.conductor_nombre ?? "").toLowerCase().includes(filtroSocio.toLowerCase())) return false;
      return true;
    });
  }, [liquidaciones, filtroEstado, filtroPeriodo, filtroSocio]);
  const margenDelMes = margen.length ? margen[margen.length - 1] : null;
  const tiempoPromedioPago = useMemo(() => {
    const conDato = margen.filter((m) => m.horas_hasta_pago_promedio != null);
    if (!conDato.length) return null;
    return conDato.reduce((acc, m) => acc + (m.horas_hasta_pago_promedio ?? 0), 0) / conDato.length;
  }, [margen]);

  const kpis = (
    <KpiRow>
      <KpiCard etiqueta="Liquidaciones emitidas" valor={String(emitidas.length)} />
      <KpiCard etiqueta="Por aprobar" valor={String(porAprobar.length)} tono={porAprobar.length > 0 ? "advertencia" : undefined} />
      <KpiCard etiqueta="Margen de comisión" valor={margenDelMes ? `${(margenDelMes.margen * 100).toFixed(1)}%` : "—"} />
      <KpiCard etiqueta="Tiempo prom. de pago" valor={tiempoPromedioPago != null ? `${tiempoPromedioPago.toFixed(1)}h` : "—"} />
    </KpiRow>
  );

  const grafico = (
    <Card>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-3)" }}>
        <h3 style={{ margin: 0, fontSize: "var(--font-size-md)" }}>Margen de comisión por mes</h3>
        <FuenteBadge tipo="compuesto" />
      </div>
      <TrendLineChart
        datos={margen.map((m) => ({ periodo: m.periodo, margen: m.margen * 100 }))}
        eje="periodo"
        series={[{ key: "margen", label: "Margen" }]}
        formatoValor={(v) => `${v.toFixed(1)}%`}
        vacio="Sin datos publicados todavía de margen de comisión."
      />
    </Card>
  );

  const lista = (
    <Card>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-3)" }}>
        <h3 style={{ margin: 0, fontSize: "var(--font-size-md)" }}>Liquidaciones del periodo por socio</h3>
        <FuenteBadge tipo="simple" />
      </div>
      <div style={{ display: "flex", gap: "var(--space-3)", flexWrap: "wrap", marginBottom: "var(--space-4)" }}>
        <div style={{ minWidth: 160 }}>
          <Select
            label="Estado"
            value={filtroEstado}
            onChange={(e) => setFiltroEstado(e.target.value)}
            options={[
              { value: "", label: "Todas" },
              { value: "EMITIDA", label: "Emitida" },
              { value: "OBSERVADA", label: "Observada" },
              { value: "APROBADA", label: "Aprobada" },
              { value: "PAGADA", label: "Pagada" },
            ]}
          />
        </div>
        <div style={{ minWidth: 160 }}>
          <Select
            label="Periodo"
            value={filtroPeriodo}
            onChange={(e) => setFiltroPeriodo(e.target.value)}
            options={[
              { value: "", label: "Todos" },
              ...periodosDisponibles.map((p) => ({ value: p, label: new Date(p).toLocaleDateString() })),
            ]}
          />
        </div>
        <div style={{ minWidth: 180 }}>
          <TextField label="Socio" value={filtroSocio} onChange={(e) => setFiltroSocio(e.target.value)} />
        </div>
      </div>
      <DataTable
        rows={liquidacionesFiltradas}
        keyField={(l) => l.id}
        vacio="No hay liquidaciones con este filtro."
        columns={[
          { header: "Socio", render: (l) => l.conductor_nombre ?? l.id.slice(0, 8) },
          { header: "Periodo", render: (l) => `${new Date(l.periodo_inicio).toLocaleDateString()} – ${new Date(l.periodo_fin).toLocaleDateString()}` },
          { header: "Bruto", render: (l) => `$${l.bruto.toFixed(2)}` },
          { header: "Comisiones", render: (l) => `$${l.comisiones.toFixed(2)}` },
          { header: "Neto", render: (l) => `$${l.neto.toFixed(2)}` },
          { header: "Estado", render: (l) => <Badge texto={l.estado} tono={l.estado === "OBSERVADA" ? "advertencia" : l.estado === "PAGADA" ? "exito" : "neutral"} /> },
        ]}
      />
    </Card>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
      <h2 style={{ margin: 0 }}>Panel de Liquidación de Comisiones</h2>
      {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
      <DashboardZ kpis={kpis} grafico={grafico} lista={lista} />
    </div>
  );
}
