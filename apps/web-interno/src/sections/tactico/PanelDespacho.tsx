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
} from "@urbanflet/shared-ui";
import { useEffect, useMemo, useState } from "react";

interface ViajeActivo {
  id: string;
  pasajero_id: string;
  conductor_id: string | null;
  estado: string;
  ts_solicitud: string;
}

interface ViajeSinConductorCancelado {
  id: string;
  estado: string;
  motivo_cancelacion: string | null;
  actor_cancelacion: string | null;
  ts_solicitud: string;
}

interface TiempoAsignacion {
  zona_origen_id: string;
  franja: string;
  segundos_promedio: number;
  segundos_p95: number;
  total_registros: number;
}

interface TasaCancelacion {
  periodo: string;
  zona_origen_id: string;
  motivo: string;
  actor: string;
  cancelados: number;
  solicitados: number;
  tasa_cancelacion: number;
}

// spec: specs/nivel-tactico/tactico_operaciones_despacho.md — Panel de Despacho y Demanda (CU-T07/T08). Patrón Z.
export function PanelDespacho() {
  const [activos, setActivos] = useState<ViajeActivo[]>([]);
  const [sinConductor, setSinConductor] = useState<ViajeSinConductorCancelado[]>([]);
  const [tiempoAsignacion, setTiempoAsignacion] = useState<TiempoAsignacion[]>([]);
  const [tasaCancelacion, setTasaCancelacion] = useState<TasaCancelacion[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [filtroZona, setFiltroZona] = useState("");
  const [filtroFranja, setFiltroFranja] = useState("");
  const [filtroDesde, setFiltroDesde] = useState("");
  const [filtroHasta, setFiltroHasta] = useState("");

  const cargar = async () => {
    try {
      const [act, sc, ta, tc] = await Promise.all([
        apiFetch<ViajeActivo[]>("/viajes/panel-tactico/activos"),
        apiFetch<ViajeSinConductorCancelado[]>("/viajes/panel-tactico/sin-conductor-cancelados"),
        apiFetch<TiempoAsignacion[]>("/viajes/panel-tactico/tiempo-asignacion"),
        apiFetch<TasaCancelacion[]>("/viajes/panel-tactico/tasa-cancelacion"),
      ]);
      setActivos(act);
      setSinConductor(sc);
      setTiempoAsignacion(ta);
      setTasaCancelacion(tc);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo cargar el panel de despacho");
    }
  };

  useEffect(() => {
    cargar();
    const id = setInterval(cargar, 15000);
    return () => clearInterval(id);
  }, []);

  const sinConductorHoy = useMemo(() => sinConductor.filter((v) => v.estado === "SIN_CONDUCTOR"), [sinConductor]);
  const tiempoPromedioGlobal = tiempoAsignacion.length
    ? tiempoAsignacion.reduce((acc, t) => acc + t.segundos_promedio, 0) / tiempoAsignacion.length
    : null;
  const tasaCancelacionGlobal = useMemo(() => {
    const totalCancelados = tasaCancelacion.reduce((acc, t) => acc + t.cancelados, 0);
    const totalSolicitados = tasaCancelacion.reduce((acc, t) => acc + t.solicitados, 0);
    return totalSolicitados > 0 ? totalCancelados / totalSolicitados : null;
  }, [tasaCancelacion]);

  const zonasDisponibles = useMemo(() => Array.from(new Set(tiempoAsignacion.map((t) => t.zona_origen_id))).sort(), [tiempoAsignacion]);
  const tiempoFiltrado = useMemo(() => {
    return tiempoAsignacion.filter((t) => {
      if (filtroZona && t.zona_origen_id !== filtroZona) return false;
      if (filtroFranja && t.franja !== filtroFranja) return false;
      return true;
    });
  }, [tiempoAsignacion, filtroZona, filtroFranja]);

  const dentroDeRango = useMemo(() => {
    return (ts: string): boolean => {
      const fecha = ts.slice(0, 10);
      if (filtroDesde && fecha < filtroDesde) return false;
      if (filtroHasta && fecha > filtroHasta) return false;
      return true;
    };
  }, [filtroDesde, filtroHasta]);
  const sinConductorFiltrado = useMemo(() => sinConductor.filter((v) => dentroDeRango(v.ts_solicitud)), [sinConductor, dentroDeRango]);
  const activosFiltrados = useMemo(() => activos.filter((v) => dentroDeRango(v.ts_solicitud)), [activos, dentroDeRango]);

  const kpis = (
    <KpiRow>
      <KpiCard etiqueta="Viajes activos" valor={String(activos.length)} />
      <KpiCard
        etiqueta="Tiempo asignación prom."
        valor={tiempoPromedioGlobal != null ? `${tiempoPromedioGlobal.toFixed(0)}s` : "—"}
      />
      <KpiCard etiqueta="Sin conductor hoy" valor={String(sinConductorHoy.length)} tono={sinConductorHoy.length > 0 ? "advertencia" : undefined} />
      <KpiCard
        etiqueta="Tasa de cancelación"
        valor={tasaCancelacionGlobal != null ? `${(tasaCancelacionGlobal * 100).toFixed(1)}%` : "—"}
      />
    </KpiRow>
  );

  const grafico = (
    <Card>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-3)" }}>
        <h3 style={{ margin: 0, fontSize: "var(--font-size-md)" }}>Tiempo de asignación por zona y franja</h3>
        <FuenteBadge tipo="compuesto" />
      </div>
      <div style={{ display: "flex", gap: "var(--space-3)", flexWrap: "wrap", marginBottom: "var(--space-3)" }}>
        <div style={{ minWidth: 160 }}>
          <Select
            label="Zona"
            value={filtroZona}
            onChange={(e) => setFiltroZona(e.target.value)}
            options={[{ value: "", label: "Todas" }, ...zonasDisponibles.map((z) => ({ value: z, label: z }))]}
          />
        </div>
        <div style={{ minWidth: 160 }}>
          <Select
            label="Franja"
            value={filtroFranja}
            onChange={(e) => setFiltroFranja(e.target.value)}
            options={[
              { value: "", label: "Todas" },
              { value: "DIURNA", label: "Diurna" },
              { value: "NOCTURNA", label: "Nocturna" },
            ]}
          />
        </div>
      </div>
      <CategoryBarChart
        datos={tiempoFiltrado.map((t) => ({ etiqueta: `${t.zona_origen_id} · ${t.franja}`, segundos: t.segundos_promedio }))}
        categoria="etiqueta"
        series={[{ key: "segundos", label: "Tiempo promedio" }]}
        formatoValor={(v) => `${v.toFixed(0)}s`}
        vacio="Sin datos publicados todavía de tiempo de asignación."
      />
    </Card>
  );

  const lista = (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
      <Card>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-3)" }}>
          <h3 style={{ margin: 0, fontSize: "var(--font-size-md)" }}>Viajes SIN_CONDUCTOR y cancelados, con motivo</h3>
          <FuenteBadge tipo="simple" />
        </div>
        <div style={{ display: "flex", gap: "var(--space-3)", flexWrap: "wrap", marginBottom: "var(--space-4)" }}>
          <div style={{ minWidth: 150 }}>
            <TextField label="Desde" type="date" value={filtroDesde} onChange={(e) => setFiltroDesde(e.target.value)} />
          </div>
          <div style={{ minWidth: 150 }}>
            <TextField label="Hasta" type="date" value={filtroHasta} onChange={(e) => setFiltroHasta(e.target.value)} />
          </div>
        </div>
        <DataTable
          rows={sinConductorFiltrado}
          keyField={(v) => v.id}
          vacio="No hay viajes SIN_CONDUCTOR ni cancelados con este filtro."
          columns={[
            { header: "Estado", render: (v) => <Badge texto={v.estado} tono={v.estado === "SIN_CONDUCTOR" ? "peligro" : "advertencia"} /> },
            { header: "Motivo", render: (v) => v.motivo_cancelacion ?? "—" },
            { header: "Actor", render: (v) => v.actor_cancelacion ?? "—" },
            { header: "Hora", render: (v) => new Date(v.ts_solicitud).toLocaleString() },
          ]}
        />
      </Card>

      <Card>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-3)" }}>
          <h3 style={{ margin: 0, fontSize: "var(--font-size-md)" }}>Viajes activos</h3>
          <FuenteBadge tipo="simple" />
        </div>
        <DataTable
          rows={activosFiltrados}
          keyField={(v) => v.id}
          vacio="No hay viajes activos con este filtro."
          columns={[
            { header: "Pasajero", render: (v) => v.pasajero_id.slice(0, 8) + "…" },
            { header: "Conductor", render: (v) => (v.conductor_id ? v.conductor_id.slice(0, 8) + "…" : "Sin asignar") },
            { header: "Estado", render: (v) => <Badge texto={v.estado} tono="neutral" /> },
            { header: "Solicitado", render: (v) => new Date(v.ts_solicitud).toLocaleTimeString() },
          ]}
        />
      </Card>
    </div>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
      <h2 style={{ margin: 0 }}>Panel de Despacho y Demanda</h2>
      {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
      <DashboardZ kpis={kpis} grafico={grafico} lista={lista} />
    </div>
  );
}
