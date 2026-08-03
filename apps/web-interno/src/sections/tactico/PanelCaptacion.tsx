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

interface Solicitud {
  id: string;
  usuario_nombre: string | null;
  cedula: string;
  estado: string;
  fecha_envio: string | null;
  canal: string | null;
}

interface SolicitudListOut {
  items: Solicitud[];
  total: number;
}

interface ReferidoPendiente {
  id: string;
  referente_id: string;
  referido_id: string;
  canal: string;
  estado_incentivo: string;
  fecha_referido: string;
}

interface ConversionCaptacion {
  periodo: string;
  canal: string;
  pct_conversion: number;
  dias_aprobacion_promedio: number | null;
  total_solicitudes: number;
}

interface AltasRetencionCanal {
  periodo: string;
  canal: string;
  altas: number;
  pct_retencion: number;
}

function diasDesde(fecha: string): number {
  return (Date.now() - new Date(fecha).getTime()) / (1000 * 60 * 60 * 24);
}

function semaforo(dias: number): { texto: string; tono: "exito" | "advertencia" | "peligro" } {
  if (dias < 3) return { texto: "En plazo", tono: "exito" };
  if (dias <= 5) return { texto: "Por vencer", tono: "advertencia" };
  return { texto: "Fuera de plazo", tono: "peligro" };
}

// spec: specs/nivel-tactico/tactico_captacion.md — Panel de Captación y Onboarding (CU-T01/T02). Patrón Z.
export function PanelCaptacion() {
  const [pendientes, setPendientes] = useState<Solicitud[]>([]);
  const [referidos, setReferidos] = useState<ReferidoPendiente[]>([]);
  const [conversion, setConversion] = useState<ConversionCaptacion[]>([]);
  const [altasRetencion, setAltasRetencion] = useState<AltasRetencionCanal[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [filtroCanal, setFiltroCanal] = useState("");
  const [filtroDesde, setFiltroDesde] = useState("");
  const [filtroHasta, setFiltroHasta] = useState("");

  const cargar = async () => {
    try {
      const [solicitudes, refs, conv, altas] = await Promise.all([
        apiFetch<SolicitudListOut>("/captacion/solicitudes?estado=ENVIADA&limit=100"),
        apiFetch<ReferidoPendiente[]>("/captacion/panel-tactico/referidos-pendientes"),
        apiFetch<ConversionCaptacion[]>("/captacion/panel-tactico/conversion"),
        apiFetch<AltasRetencionCanal[]>("/captacion/panel-tactico/altas-retencion"),
      ]);
      setPendientes(solicitudes.items);
      setReferidos(refs);
      setConversion(conv);
      setAltasRetencion(altas);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo cargar el panel de captación");
    }
  };

  useEffect(() => {
    cargar();
  }, []);

  const fueraDePlazo = useMemo(
    () => pendientes.filter((s) => s.fecha_envio && diasDesde(s.fecha_envio) > 5).length,
    [pendientes],
  );
  const conversionDelMes = conversion.length
    ? conversion.reduce((acc, c) => acc + c.pct_conversion, 0) / conversion.length
    : null;
  const diasPromedio = useMemo(() => {
    const conDato = conversion.filter((c) => c.dias_aprobacion_promedio != null);
    if (!conDato.length) return null;
    return conDato.reduce((acc, c) => acc + (c.dias_aprobacion_promedio ?? 0), 0) / conDato.length;
  }, [conversion]);
  const retencionPromedio = altasRetencion.length
    ? altasRetencion.reduce((acc, a) => acc + a.pct_retencion, 0) / altasRetencion.length
    : null;

  const canalesDisponibles = useMemo(
    () => Array.from(new Set([...pendientes.map((p) => p.canal ?? ""), ...referidos.map((r) => r.canal)])).filter(Boolean).sort(),
    [pendientes, referidos],
  );

  const pendientesFiltrados = useMemo(() => {
    return pendientes.filter((s) => {
      if (filtroCanal && s.canal !== filtroCanal) return false;
      const fecha = s.fecha_envio?.slice(0, 10);
      if (filtroDesde && (!fecha || fecha < filtroDesde)) return false;
      if (filtroHasta && (!fecha || fecha > filtroHasta)) return false;
      return true;
    });
  }, [pendientes, filtroCanal, filtroDesde, filtroHasta]);

  const referidosFiltrados = useMemo(() => {
    return referidos.filter((r) => {
      if (filtroCanal && r.canal !== filtroCanal) return false;
      const fecha = r.fecha_referido.slice(0, 10);
      if (filtroDesde && fecha < filtroDesde) return false;
      if (filtroHasta && fecha > filtroHasta) return false;
      return true;
    });
  }, [referidos, filtroCanal, filtroDesde, filtroHasta]);

  const periodos = useMemo(() => Array.from(new Set(conversion.map((c) => c.periodo))).sort(), [conversion]);
  const canalesConversion = useMemo(() => Array.from(new Set(conversion.map((c) => c.canal))), [conversion]);
  const conversionPivot = useMemo(
    () =>
      periodos.map((periodo) => {
        const fila: Record<string, string | number> = { periodo };
        for (const canal of canalesConversion) {
          const dato = conversion.find((c) => c.periodo === periodo && c.canal === canal);
          if (dato) fila[canal] = dato.pct_conversion * 100;
        }
        return fila;
      }),
    [periodos, canalesConversion, conversion],
  );

  const kpis = (
    <KpiRow>
      <KpiCard etiqueta="Solicitudes pendientes" valor={String(pendientes.length)} tono={fueraDePlazo > 0 ? "peligro" : undefined} />
      <KpiCard etiqueta="Conversión del mes" valor={conversionDelMes != null ? `${(conversionDelMes * 100).toFixed(1)}%` : "—"} />
      <KpiCard etiqueta="Tiempo prom. aprobación" valor={diasPromedio != null ? `${diasPromedio.toFixed(1)}d` : "—"} />
      <KpiCard etiqueta="Retención a 90d" valor={retencionPromedio != null ? `${(retencionPromedio * 100).toFixed(1)}%` : "—"} />
    </KpiRow>
  );

  const grafico = (
    <Card>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-3)" }}>
        <h3 style={{ margin: 0, fontSize: "var(--font-size-md)" }}>Conversión de onboarding por canal</h3>
        <FuenteBadge tipo="compuesto" />
      </div>
      <TrendLineChart
        datos={conversionPivot}
        eje="periodo"
        series={canalesConversion.map((c) => ({ key: c, label: c }))}
        formatoValor={(v) => `${v.toFixed(1)}%`}
        vacio="Sin datos publicados todavía de conversión por canal."
      />
      <p style={{ marginTop: "var(--space-3)", fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>
        Nota: "retención a 90 días" es una aproximación (estado ACTIVO al momento del snapshot, no un
        re-chequeo de actividad real a los 90 días) — no existe un job que reobserve usuarios periódicamente.
      </p>
    </Card>
  );

  const lista = (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
      <Card>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-3)" }}>
          <h3 style={{ margin: 0, fontSize: "var(--font-size-md)" }}>Solicitudes pendientes de verificación</h3>
          <FuenteBadge tipo="simple" />
        </div>
        <div style={{ display: "flex", gap: "var(--space-3)", flexWrap: "wrap", marginBottom: "var(--space-4)" }}>
          <div style={{ minWidth: 160 }}>
            <Select
              label="Canal"
              value={filtroCanal}
              onChange={(e) => setFiltroCanal(e.target.value)}
              options={[{ value: "", label: "Todos" }, ...canalesDisponibles.map((c) => ({ value: c, label: c }))]}
            />
          </div>
          <div style={{ minWidth: 150 }}>
            <TextField label="Desde" type="date" value={filtroDesde} onChange={(e) => setFiltroDesde(e.target.value)} />
          </div>
          <div style={{ minWidth: 150 }}>
            <TextField label="Hasta" type="date" value={filtroHasta} onChange={(e) => setFiltroHasta(e.target.value)} />
          </div>
        </div>
        <DataTable
          rows={pendientesFiltrados}
          keyField={(s) => s.id}
          vacio="No hay solicitudes pendientes de verificación con este filtro."
          columns={[
            { header: "Postulante", render: (s) => s.usuario_nombre ?? s.cedula },
            { header: "Cédula", render: (s) => s.cedula },
            { header: "Canal", render: (s) => s.canal ?? "—" },
            {
              header: "Días desde envío",
              render: (s) => (s.fecha_envio ? diasDesde(s.fecha_envio).toFixed(1) : "—"),
            },
            {
              header: "Plazo",
              render: (s) => {
                if (!s.fecha_envio) return "—";
                const { texto, tono } = semaforo(diasDesde(s.fecha_envio));
                return <Badge texto={texto} tono={tono} />;
              },
            },
          ]}
        />
      </Card>

      <Card>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-3)" }}>
          <h3 style={{ margin: 0, fontSize: "var(--font-size-md)" }}>Referidos y estado de su incentivo</h3>
          <FuenteBadge tipo="simple" />
        </div>
        <DataTable
          rows={referidosFiltrados}
          keyField={(r) => r.id}
          vacio="No hay referidos con incentivo pendiente o acreditado con este filtro."
          columns={[
            { header: "Referente", render: (r) => r.referente_id.slice(0, 8) + "…" },
            { header: "Referido", render: (r) => r.referido_id.slice(0, 8) + "…" },
            { header: "Canal", render: (r) => r.canal },
            {
              header: "Incentivo",
              render: (r) => <Badge texto={r.estado_incentivo} tono={r.estado_incentivo === "ACREDITADO" ? "exito" : "advertencia"} />,
            },
            { header: "Fecha", render: (r) => new Date(r.fecha_referido).toLocaleDateString() },
          ]}
        />
      </Card>
    </div>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
      <h2 style={{ margin: 0 }}>Panel de Captación y Onboarding</h2>
      {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
      <DashboardZ kpis={kpis} grafico={grafico} lista={lista} />
    </div>
  );
}
