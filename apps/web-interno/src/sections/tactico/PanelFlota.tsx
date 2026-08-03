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

// Nota: el spec (specs/nivel-tactico/tactico_flota.md) pide filtro por zona
// además de franja horaria, pero `fact_ubicacion_flota` no tiene dimensión
// zona (gap conocido, documentado en CLAUDE.md §7 "Coordinación de Flota").
// El filtro de zona queda deshabilitado con la explicación, no oculto.

interface EstadoVehiculo {
  vehiculo_id: string;
  vehiculo_placa: string | null;
  conductor_id: string;
  conductor_nombre: string | null;
  estado_servicio: string;
  ts_servidor: string | null;
  sin_senal: boolean;
}

interface FlotaActivaFranja {
  franja: string;
  pct_disponible: number;
  total_registros: number;
}

const tonoPorEstado: Record<string, "neutral" | "exito" | "advertencia" | "peligro"> = {
  DISPONIBLE: "exito",
  OCUPADO: "advertencia",
  "SIN_SEÑAL": "peligro",
};

// spec: specs/nivel-tactico/tactico_flota.md — Panel de Flota en Vivo y Disponibilidad (CU-T05/T06). Patrón Z.
export function PanelFlota() {
  const [vehiculos, setVehiculos] = useState<EstadoVehiculo[]>([]);
  const [franjas, setFranjas] = useState<FlotaActivaFranja[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [filtroFranja, setFiltroFranja] = useState("");

  const cargar = async () => {
    try {
      const [tablero, franjaActiva] = await Promise.all([
        apiFetch<EstadoVehiculo[]>("/flota/tablero"),
        apiFetch<FlotaActivaFranja[]>("/flota/panel-tactico/franja-activa"),
      ]);
      setVehiculos(tablero);
      setFranjas(franjaActiva);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo cargar el panel de flota");
    }
  };

  useEffect(() => {
    cargar();
    const id = setInterval(cargar, 10000);
    return () => clearInterval(id);
  }, []);

  const sinSenal = useMemo(() => vehiculos.filter((v) => v.sin_senal), [vehiculos]);
  const enServicio = vehiculos.length;
  const disponibles = vehiculos.filter((v) => v.estado_servicio === "DISPONIBLE").length;
  const pctFlotaActiva = franjas.length
    ? franjas.reduce((acc, f) => acc + f.pct_disponible, 0) / franjas.length
    : null;
  const franjasFiltradas = useMemo(
    () => (filtroFranja ? franjas.filter((f) => f.franja === filtroFranja) : franjas),
    [franjas, filtroFranja],
  );

  const kpis = (
    <KpiRow>
      <KpiCard etiqueta="En servicio" valor={String(enServicio)} />
      <KpiCard etiqueta="Disponibles" valor={String(disponibles)} />
      <KpiCard etiqueta="Sin señal" valor={String(sinSenal.length)} tono={sinSenal.length > 0 ? "peligro" : undefined} />
      <KpiCard etiqueta="% flota activa" valor={pctFlotaActiva != null ? `${pctFlotaActiva.toFixed(1)}%` : "—"} />
    </KpiRow>
  );

  const grafico = (
    <Card>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-3)" }}>
        <h3 style={{ margin: 0, fontSize: "var(--font-size-md)" }}>% de flota activa por franja horaria</h3>
        <FuenteBadge tipo="compuesto" />
      </div>
      <div style={{ display: "flex", gap: "var(--space-3)", flexWrap: "wrap", marginBottom: "var(--space-3)" }}>
        <div style={{ minWidth: 160 }}>
          <Select
            label="Franja"
            value={filtroFranja}
            onChange={(e) => setFiltroFranja(e.target.value)}
            options={[{ value: "", label: "Todas" }, ...franjas.map((f) => ({ value: f.franja, label: f.franja }))]}
          />
        </div>
        <div style={{ minWidth: 160 }}>
          <TextField label="Zona" value="" onChange={() => {}} disabled placeholder="No disponible" />
        </div>
      </div>
      <p style={{ marginTop: 0, fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>
        Filtro por zona no disponible todavía — el dato publicado agrega solo por franja (ver nota en CLAUDE.md).
      </p>
      <CategoryBarChart
        datos={franjasFiltradas}
        categoria="franja"
        series={[{ key: "pct_disponible", label: "% disponible" }]}
        formatoValor={(v) => `${v.toFixed(1)}%`}
        vacio="Sin datos publicados todavía para % de flota activa por franja."
      />
    </Card>
  );

  const lista = (
    <Card>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-3)" }}>
        <h3 style={{ margin: 0, fontSize: "var(--font-size-md)" }}>Vehículos sin señal o en alerta</h3>
        <FuenteBadge tipo="simple" />
      </div>
      <DataTable
        rows={sinSenal}
        keyField={(v) => v.vehiculo_id}
        vacio="No hay vehículos sin señal en este momento."
        columns={[
          {
            header: "Vehículo",
            render: (v) => v.vehiculo_placa ?? `Sin placa (${v.vehiculo_id.slice(0, 8)}…)`,
          },
          {
            header: "Conductor",
            render: (v) => v.conductor_nombre ?? `Sin nombre (${v.conductor_id.slice(0, 8)}…)`,
          },
          { header: "Estado", render: (v) => <Badge texto={v.estado_servicio} tono={tonoPorEstado[v.estado_servicio] ?? "neutral"} /> },
          {
            header: "Última señal",
            render: (v) => (v.ts_servidor ? new Date(v.ts_servidor).toLocaleString() : "Sin señal registrada"),
          },
        ]}
      />
    </Card>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
      <h2 style={{ margin: 0 }}>Panel de Flota en Vivo y Disponibilidad</h2>
      {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
      <DashboardZ kpis={kpis} grafico={grafico} lista={lista} />
    </div>
  );
}
