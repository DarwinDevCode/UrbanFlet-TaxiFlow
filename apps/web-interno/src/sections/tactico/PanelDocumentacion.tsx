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
  TrendLineChart,
} from "@urbanflet/shared-ui";
import { useEffect, useMemo, useState } from "react";

interface DocumentoVencimiento {
  documento_id: string;
  tipo: string;
  propietario_tipo: string;
  propietario_id: string;
  propietario_nombre: string | null;
  fecha_vencimiento: string | null;
  estado_verificacion: string;
  dias_restantes: number | null;
}

interface DocumentacionVigente {
  tipo: string;
  pct_vigente: number;
  total_registros: number;
  fecha_datos: string | null;
}

// spec: specs/nivel-tactico/tactico_cumplimiento.md — Panel de Vigencia Documental (CU-T10/OT6.1). Patrón Z.
export function PanelDocumentacion() {
  const [porVencer, setPorVencer] = useState<DocumentoVencimiento[]>([]);
  const [vigentePorTipo, setVigentePorTipo] = useState<DocumentacionVigente[]>([]);
  const [tendencia, setTendencia] = useState<DocumentacionVigente[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [filtroTipo, setFiltroTipo] = useState("");
  const [filtroDesde, setFiltroDesde] = useState("");
  const [filtroHasta, setFiltroHasta] = useState("");

  const cargar = async () => {
    try {
      const [documentos, vigente, historial] = await Promise.all([
        apiFetch<DocumentoVencimiento[]>("/cumplimiento/panel-tactico/documentos-por-vencer"),
        apiFetch<DocumentacionVigente[]>("/cumplimiento/panel-tactico/documentacion-vigente"),
        apiFetch<DocumentacionVigente[]>("/cumplimiento/panel-tactico/documentacion-tendencia"),
      ]);
      setPorVencer(documentos);
      setVigentePorTipo(vigente);
      setTendencia(historial);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo cargar el panel de documentación");
    }
  };

  useEffect(() => {
    cargar();
  }, []);

  const vencidos = useMemo(() => porVencer.filter((d) => (d.dias_restantes ?? 0) < 0), [porVencer]);
  const porVencer30d = useMemo(() => porVencer.filter((d) => (d.dias_restantes ?? 0) >= 0), [porVencer]);
  const bloqueados = useMemo(() => porVencer.filter((d) => d.estado_verificacion === "BLOQUEADO"), [porVencer]);
  const pctVigentePromedio = vigentePorTipo.length
    ? vigentePorTipo.reduce((acc, v) => acc + v.pct_vigente, 0) / vigentePorTipo.length
    : null;

  const tiposDisponibles = useMemo(() => Array.from(new Set(porVencer.map((d) => d.tipo))).sort(), [porVencer]);
  const documentosFiltrados = useMemo(() => {
    return porVencer.filter((d) => {
      if (filtroTipo && d.tipo !== filtroTipo) return false;
      const fecha = d.fecha_vencimiento?.slice(0, 10);
      if (filtroDesde && (!fecha || fecha < filtroDesde)) return false;
      if (filtroHasta && (!fecha || fecha > filtroHasta)) return false;
      return true;
    });
  }, [porVencer, filtroTipo, filtroDesde, filtroHasta]);

  const fechasTendencia = useMemo(() => Array.from(new Set(tendencia.map((t) => t.fecha_datos))).sort(), [tendencia]);
  const tiposTendencia = useMemo(() => Array.from(new Set(tendencia.map((t) => t.tipo))), [tendencia]);
  const tendenciaPivot = useMemo(
    () =>
      fechasTendencia.map((fecha) => {
        const fila: Record<string, string | number> = { fecha: fecha ?? "" };
        for (const tipo of tiposTendencia) {
          const dato = tendencia.find((t) => t.fecha_datos === fecha && t.tipo === tipo);
          if (dato) fila[tipo] = dato.pct_vigente;
        }
        return fila;
      }),
    [fechasTendencia, tiposTendencia, tendencia],
  );

  const kpis = (
    <KpiRow>
      <KpiCard etiqueta="Vencidos" valor={String(vencidos.length)} tono={vencidos.length > 0 ? "peligro" : undefined} />
      <KpiCard etiqueta="Por vencer (≤30d)" valor={String(porVencer30d.length)} tono={porVencer30d.length > 0 ? "advertencia" : undefined} />
      <KpiCard etiqueta="% vigente" valor={pctVigentePromedio != null ? `${pctVigentePromedio.toFixed(1)}%` : "—"} />
      <KpiCard etiqueta="Bloqueados" valor={String(bloqueados.length)} tono={bloqueados.length > 0 ? "peligro" : undefined} />
    </KpiRow>
  );

  const grafico = (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
      <Card>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-3)" }}>
          <h3 style={{ margin: 0, fontSize: "var(--font-size-md)" }}>Documentación vigente por tipo</h3>
          <FuenteBadge tipo="compuesto" />
        </div>
        <CategoryBarChart
          datos={vigentePorTipo}
          categoria="tipo"
          series={[{ key: "pct_vigente", label: "% vigente" }]}
          formatoValor={(v) => `${v.toFixed(1)}%`}
          vacio="Sin datos publicados todavía — no hay documentos registrados en el sistema (carga de documentos de postulación es backlog consciente, ver CLAUDE.md)."
          alto={220}
        />
      </Card>
      <Card>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-3)" }}>
          <h3 style={{ margin: 0, fontSize: "var(--font-size-md)" }}>Tendencia mensual de % vigente</h3>
          <FuenteBadge tipo="compuesto" />
        </div>
        <TrendLineChart
          datos={tendenciaPivot}
          eje="fecha"
          series={tiposTendencia.map((t) => ({ key: t, label: t }))}
          formatoValor={(v) => `${v.toFixed(1)}%`}
          vacio="Sin historial publicado todavía."
          alto={220}
        />
      </Card>
    </div>
  );

  const lista = (
    <Card>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-3)" }}>
        <h3 style={{ margin: 0, fontSize: "var(--font-size-md)" }}>Documentos vencidos y por vencer (≤ 30 días)</h3>
        <FuenteBadge tipo="simple" />
      </div>
      <div style={{ display: "flex", gap: "var(--space-3)", flexWrap: "wrap", marginBottom: "var(--space-4)" }}>
        <div style={{ minWidth: 180 }}>
          <Select
            label="Tipo de documento"
            value={filtroTipo}
            onChange={(e) => setFiltroTipo(e.target.value)}
            options={[{ value: "", label: "Todos" }, ...tiposDisponibles.map((t) => ({ value: t, label: t }))]}
          />
        </div>
        <div style={{ minWidth: 150 }}>
          <TextField label="Vence desde" type="date" value={filtroDesde} onChange={(e) => setFiltroDesde(e.target.value)} />
        </div>
        <div style={{ minWidth: 150 }}>
          <TextField label="Vence hasta" type="date" value={filtroHasta} onChange={(e) => setFiltroHasta(e.target.value)} />
        </div>
      </div>
      <DataTable
        rows={documentosFiltrados}
        keyField={(d) => d.documento_id}
        vacio="No hay documentos vencidos ni por vencer con este filtro."
        columns={[
          { header: "Tipo", render: (d) => d.tipo },
          { header: "Propietario", render: (d) => d.propietario_nombre ?? `${d.propietario_tipo} (${d.propietario_id.slice(0, 8)}…)` },
          { header: "Vence", render: (d) => (d.fecha_vencimiento ? new Date(d.fecha_vencimiento).toLocaleDateString() : "—") },
          {
            header: "Días restantes",
            render: (d) =>
              d.dias_restantes == null ? (
                "—"
              ) : d.dias_restantes < 0 ? (
                <Badge texto={`Vencido hace ${Math.abs(d.dias_restantes)}d`} tono="peligro" />
              ) : (
                <Badge texto={`${d.dias_restantes}d`} tono={d.dias_restantes <= 7 ? "advertencia" : "neutral"} />
              ),
          },
          { header: "Estado", render: (d) => <Badge texto={d.estado_verificacion} tono={d.estado_verificacion === "BLOQUEADO" ? "peligro" : "neutral"} /> },
        ]}
      />
    </Card>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
      <h2 style={{ margin: 0 }}>Panel de Vigencia Documental</h2>
      {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
      <DashboardZ kpis={kpis} grafico={grafico} lista={lista} />
    </div>
  );
}
