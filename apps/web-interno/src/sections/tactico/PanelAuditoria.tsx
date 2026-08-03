import {
  ApiError,
  apiFetch,
  Badge,
  Card,
  CategoryBarChart,
  DashboardF,
  DataTable,
  FuenteBadge,
  KpiCard,
  KpiRow,
  Select,
  TextField,
} from "@urbanflet/shared-ui";
import { useEffect, useMemo, useState } from "react";

interface EventoAuditoria {
  evento_id: number;
  ts: string;
  actor_id: string | null;
  rol: string | null;
  accion: string;
  entidad: string;
  resultado: string;
}

interface EventosPage {
  items: EventoAuditoria[];
  total: number;
}

interface UsoIntegracion {
  endpoint: string;
  conteo: number;
  total_global: number;
}

// spec: specs/nivel-tactico/tactico_cumplimiento.md — Panel de Auditoría e
// Integraciones (CU-T13/T03), único de los 9 dashboards con patrón F: la
// tabla de eventos es el elemento dominante en ancho y altura; el gráfico
// secundario queda más angosto que la lista (no a la mitad como en Z), y
// los KPIs son una franja delgada de contexto arriba.
export function PanelAuditoria() {
  const [eventos, setEventos] = useState<EventoAuditoria[]>([]);
  const [totalEventosHoy, setTotalEventosHoy] = useState(0);
  const [integraciones, setIntegraciones] = useState<UsoIntegracion[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [actorInput, setActorInput] = useState("");
  const [filtroActor, setFiltroActor] = useState("");
  const [filtroResultado, setFiltroResultado] = useState("DENEGADO");
  const [filtroAccion, setFiltroAccion] = useState("");
  const [filtroDesde, setFiltroDesde] = useState("");
  const [filtroHasta, setFiltroHasta] = useState("");

  const cargar = async () => {
    try {
      const params = new URLSearchParams();
      if (filtroActor) params.set("actor_id", filtroActor);
      if (filtroResultado) params.set("resultado", filtroResultado);
      if (filtroAccion) params.set("accion", filtroAccion);
      if (filtroDesde) params.set("desde", new Date(filtroDesde).toISOString());
      if (filtroHasta) params.set("hasta", new Date(filtroHasta + "T23:59:59").toISOString());
      params.set("tamanio_pagina", "100");

      const hoyInicio = new Date();
      hoyInicio.setHours(0, 0, 0, 0);
      const paramsHoy = new URLSearchParams({ desde: hoyInicio.toISOString(), tamanio_pagina: "1" });

      const [pagina, hoy, uso] = await Promise.all([
        apiFetch<EventosPage>(`/auditoria/eventos?${params.toString()}`),
        apiFetch<EventosPage>(`/auditoria/eventos?${paramsHoy.toString()}`),
        apiFetch<UsoIntegracion[]>("/auditoria/panel-tactico/uso-integraciones"),
      ]);
      setEventos(pagina.items);
      setTotalEventosHoy(hoy.total);
      setIntegraciones(uso);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo cargar el panel de auditoría");
    }
  };

  useEffect(() => {
    cargar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtroActor, filtroResultado, filtroAccion, filtroDesde, filtroHasta]);

  const accesosDenegados = useMemo(() => eventos.filter((e) => e.resultado === "DENEGADO").length, [eventos]);
  const endpointsActivos = new Set(integraciones.map((i) => i.endpoint)).size;

  const buscar = () => setFiltroActor(actorInput.trim());

  const kpis = (
    <>
      <KpiRow>
        <KpiCard etiqueta="Eventos hoy" valor={String(totalEventosHoy)} />
        <KpiCard etiqueta="Accesos denegados" valor={String(accesosDenegados)} tono={accesosDenegados > 0 ? "peligro" : undefined} />
        <KpiCard etiqueta="Endpoints activos" valor={String(endpointsActivos)} />
        <KpiCard etiqueta="% error API" valor="—" />
      </KpiRow>
      <p style={{ margin: "var(--space-2) 0 0", fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>
        "% error API" no disponible — no existe dominio de credenciales de integración en el sistema (backlog
        consciente); el gráfico usa solo conteo de solicitudes por endpoint, derivado de la bitácora.
      </p>
    </>
  );

  const grafico = (
    <Card>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-3)" }}>
        <h3 style={{ margin: 0, fontSize: "var(--font-size-md)" }}>Uso de API por endpoint</h3>
        <FuenteBadge tipo="compuesto" />
      </div>
      <CategoryBarChart
        datos={integraciones}
        categoria="endpoint"
        series={[{ key: "conteo", label: "Solicitudes" }]}
        vacio="Sin datos publicados todavía de uso de integraciones."
        alto={520}
      />
    </Card>
  );

  const lista = (
    <Card>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-3)" }}>
        <h3 style={{ margin: 0, fontSize: "var(--font-size-md)" }}>Bitácora — eventos de auditoría</h3>
        <FuenteBadge tipo="simple" />
      </div>
      <div style={{ display: "flex", gap: "var(--space-3)", flexWrap: "wrap", alignItems: "flex-end", marginBottom: "var(--space-3)" }}>
        <div style={{ minWidth: 200 }}>
          <TextField
            label="Actor (id)"
            value={actorInput}
            onChange={(e) => setActorInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && buscar()}
          />
        </div>
        <div style={{ minWidth: 180 }}>
          <TextField label="Acción" value={filtroAccion} onChange={(e) => setFiltroAccion(e.target.value)} />
        </div>
        <div style={{ minWidth: 170 }}>
          <Select
            label="Resultado"
            value={filtroResultado}
            onChange={(e) => setFiltroResultado(e.target.value)}
            options={[
              { value: "", label: "Todos" },
              { value: "DENEGADO", label: "Denegado" },
              { value: "OK", label: "OK" },
            ]}
          />
        </div>
        <div style={{ minWidth: 140 }}>
          <TextField label="Desde" type="date" value={filtroDesde} onChange={(e) => setFiltroDesde(e.target.value)} />
        </div>
        <div style={{ minWidth: 140 }}>
          <TextField label="Hasta" type="date" value={filtroHasta} onChange={(e) => setFiltroHasta(e.target.value)} />
        </div>
      </div>
      <DataTable
        rows={eventos}
        keyField={(e) => String(e.evento_id)}
        vacio="No hay eventos con este filtro."
        altoMaximo={620}
        columns={[
          { header: "Actor", render: (e) => e.actor_id ?? "—" },
          { header: "Rol", width: "160px", render: (e) => e.rol ?? "—" },
          { header: "Acción", render: (e) => e.accion },
          { header: "Entidad", render: (e) => e.entidad },
          { header: "Resultado", render: (e) => <Badge texto={e.resultado} tono={e.resultado === "DENEGADO" ? "peligro" : "exito"} /> },
          { header: "Hora", render: (e) => new Date(e.ts).toLocaleString() },
        ]}
      />
    </Card>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <h2 style={{ margin: 0 }}>Panel de Auditoría e Integraciones</h2>
      {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
      <DashboardF kpis={kpis} grafico={grafico} lista={lista} />
    </div>
  );
}
