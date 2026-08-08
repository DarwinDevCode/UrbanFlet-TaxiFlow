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
  TrendLineChart,
  useSwr,
} from "@urbanflet/shared-ui";
import { useMemo, useState } from "react";
import { FilaFiltros, NotaLimitacion, TituloTarjeta } from "./comunes";
import { entero, OPCIONES_VENTANA, pct, segundos, tonoVariacion, variacion } from "./formato";

// spec: specs/nivel-estrategico/nivel_estrategico.md §3.2.a — Panel de
// Confiabilidad y Disponibilidad del Servicio (OE2a). Patrón Z.
const RECURSO = "/viajes/panel-estrategico/confiabilidad";

const SIN_ASIGNACION: PuntoAsignacion[] = [];
const SIN_CANCELACION: PuntoCancelacion[] = [];
const SIN_FLOTA: PuntoFlota[] = [];
const SIN_FRANJAS: FranjaCobertura[] = [];
const SIN_FRANJAS_ASIGNACION: FranjaAsignacion[] = [];

interface PuntoAsignacion {
  periodo: string;
  segundos_promedio: number;
  total_registros: number;
}

interface PuntoCancelacion {
  periodo: string;
  cancelados: number;
  sin_conductor: number;
}

interface PuntoFlota {
  periodo: string;
  pct_disponible: number;
  total_registros: number;
}

interface FranjaCobertura {
  franja: string;
  pct_disponible: number;
  total_registros: number;
}

interface FranjaAsignacion {
  franja: string;
  segundos_promedio: number;
  total_registros: number;
}

interface PanelConfiabilidadOut {
  kpis: {
    segundos_asignacion_promedio: number | null;
    cancelaciones_periodo: number | null;
    variacion_cancelaciones_pct: number | null;
    tasa_cancelacion: number | null;
    pct_flota_activa: number | null;
    franja_menor_cobertura: string | null;
  };
  tendencia_asignacion: PuntoAsignacion[];
  tendencia_cancelacion: PuntoCancelacion[];
  tendencia_flota: PuntoFlota[];
  franjas: FranjaCobertura[];
  franjas_asignacion: FranjaAsignacion[];
  metadata: {
    meses: number;
    zona_disponible: boolean;
    tasa_cancelacion_disponible: boolean;
    fuentes: string[];
  };
}

export function PanelConfiabilidad() {
  const [meses, setMeses] = useState("6");
  const [filtroFranja, setFiltroFranja] = useState("");

  const clave = `${RECURSO}?meses=${meses}`;
  const { data, error: errorCarga } = useSwr<PanelConfiabilidadOut>(clave, () =>
    apiFetch<PanelConfiabilidadOut>(clave),
  );
  const error = errorCarga
    ? errorCarga instanceof ApiError
      ? errorCarga.message
      : "No se pudo cargar el panel de confiabilidad"
    : null;

  const k = data?.kpis;
  const tendenciaAsignacion = data?.tendencia_asignacion ?? SIN_ASIGNACION;
  const tendenciaCancelacion = data?.tendencia_cancelacion ?? SIN_CANCELACION;
  const tendenciaFlota = data?.tendencia_flota ?? SIN_FLOTA;
  const franjas = data?.franjas ?? SIN_FRANJAS;
  const franjasAsignacion = data?.franjas_asignacion ?? SIN_FRANJAS_ASIGNACION;
  const zonaDisponible = data?.metadata.zona_disponible ?? false;
  const tasaDisponible = data?.metadata.tasa_cancelacion_disponible ?? false;

  const serieFlota = useMemo(
    () => tendenciaFlota.map((p) => ({ periodo: p.periodo, pct: p.pct_disponible * 100 })),
    [tendenciaFlota],
  );

  const franjasOrdenadas = useMemo(
    () => [...franjas].sort((a, b) => a.pct_disponible - b.pct_disponible),
    [franjas],
  );
  const franjasFiltradas = useMemo(
    () => (filtroFranja ? franjasOrdenadas.filter((f) => f.franja === filtroFranja) : franjasOrdenadas),
    [franjasOrdenadas, filtroFranja],
  );

  const kpis = (
    <>
      <KpiRow>
        <KpiCard etiqueta="Tiempo de asignación prom." valor={segundos(k?.segundos_asignacion_promedio)} />
        <KpiCard etiqueta="Tasa de cancelación" valor={pct(k?.tasa_cancelacion)} />
        <KpiCard
          etiqueta="Cancelaciones del periodo"
          valor={entero(k?.cancelaciones_periodo)}
          tono={tonoVariacion(k?.variacion_cancelaciones_pct, { subirEsBueno: false })}
        />
        <KpiCard
          etiqueta="Flota activa promedio"
          valor={pct(k?.pct_flota_activa)}
          tono={k?.pct_flota_activa != null && k.pct_flota_activa < 0.8 ? "advertencia" : undefined}
        />
        <KpiCard etiqueta="Franja con menor cobertura" valor={k?.franja_menor_cobertura ?? "—"} />
      </KpiRow>
      {!tasaDisponible && (
        <NotaLimitacion>
          "Tasa de cancelación" no disponible como porcentaje —{" "}
          <code>rpt_tasa_cancelacion</code> solo publica filas de viajes ya cancelados, así que no tiene
          denominador de solicitados para consolidar. Se muestra el conteo absoluto y su variación
          ({variacion(k?.variacion_cancelaciones_pct)}) en vez de un porcentaje fabricado.
        </NotaLimitacion>
      )}
    </>
  );

  const grafico = (
    <Card>
      <TituloTarjeta titulo="Tiempo de asignación (tendencia)" extra={<FuenteBadge tipo="compuesto" />} />
      <FilaFiltros>
        <div style={{ minWidth: 180 }}>
          <Select
            label="Ventana (meses)"
            value={meses}
            onChange={(e) => setMeses(e.target.value)}
            options={OPCIONES_VENTANA}
          />
        </div>
      </FilaFiltros>
      <TrendLineChart
        datos={tendenciaAsignacion}
        eje="periodo"
        series={[{ key: "segundos_promedio", label: "Segundos hasta asignación" }]}
        formatoValor={(v) => `${v.toFixed(0)}s`}
        alto={200}
        vacio="Sin cortes publicados todavía de tiempo de asignación."
      />
      <TituloTarjeta titulo="Cancelaciones y demanda desatendida" />
      <TrendLineChart
        datos={tendenciaCancelacion}
        eje="periodo"
        series={[
          { key: "cancelados", label: "Cancelados" },
          { key: "sin_conductor", label: "Sin conductor" },
        ]}
        formatoValor={(v) => entero(v)}
        alto={200}
        vacio="Sin cortes publicados todavía de cancelaciones."
      />
      <TituloTarjeta titulo="Flota activa (%)" />
      <TrendLineChart
        datos={serieFlota}
        eje="periodo"
        series={[{ key: "pct", label: "% disponible" }]}
        formatoValor={(v) => `${v.toFixed(1)}%`}
        alto={200}
        vacio="Sin cortes publicados todavía de disponibilidad de flota."
      />
    </Card>
  );

  const lista = (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
      <Card>
        <TituloTarjeta titulo="Franjas con menor disponibilidad" extra={<FuenteBadge tipo="compuesto" />} />
        <FilaFiltros>
          <div style={{ minWidth: 180 }}>
            <Select
              label="Franja horaria"
              value={filtroFranja}
              onChange={(e) => setFiltroFranja(e.target.value)}
              options={[
                { value: "", label: "Todas" },
                ...franjas.map((f) => ({ value: f.franja, label: f.franja })),
              ]}
            />
          </div>
          <div style={{ minWidth: 180 }}>
            <Select label="Zona" value="" onChange={() => undefined} disabled options={[{ value: "", label: "No disponible" }]} />
          </div>
        </FilaFiltros>
        <DataTable
          rows={franjasFiltradas}
          keyField={(f) => f.franja}
          vacio="Sin datos de cobertura por franja."
          columns={[
            { header: "Franja", render: (f) => f.franja },
            {
              header: "Disponibilidad",
              render: (f) => (
                <Badge
                  texto={pct(f.pct_disponible)}
                  tono={f.pct_disponible >= 0.9 ? "exito" : f.pct_disponible >= 0.7 ? "advertencia" : "peligro"}
                />
              ),
            },
            { header: "Registros", render: (f) => entero(f.total_registros) },
          ]}
        />
        {!zonaDisponible && (
          <NotaLimitacion>
            Filtro y desglose por <strong>zona</strong> no disponibles:{" "}
            <code>viajes.zona_origen_id</code>/<code>zona_destino_id</code> nunca se resuelven en la
            operación (0 de ~1,3 M de viajes), así que no existe esa dimensión en ninguna vista{" "}
            <code>rpt_*</code>. La cobertura se analiza solo por franja horaria.
          </NotaLimitacion>
        )}
      </Card>

      <Card>
        <TituloTarjeta titulo="Tiempo de asignación por franja tarifaria" extra={<FuenteBadge tipo="compuesto" />} />
        <DataTable
          rows={franjasAsignacion}
          keyField={(f) => f.franja}
          vacio="Sin datos de asignación por franja."
          columns={[
            { header: "Franja", render: (f) => f.franja },
            { header: "Segundos prom.", render: (f) => segundos(f.segundos_promedio) },
            { header: "Viajes", render: (f) => entero(f.total_registros) },
          ]}
        />
        <NotaLimitacion>
          Dos taxonomías distintas de "franja" conviven a propósito: los buckets de 6 h vienen del ping
          GPS de flota, y DIURNA/NOCTURNA de la franja tarifaria del viaje.
        </NotaLimitacion>
      </Card>
    </div>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
      <h2 style={{ margin: 0 }}>Panel de Confiabilidad y Disponibilidad del Servicio</h2>
      {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
      <DashboardZ kpis={kpis} grafico={grafico} lista={lista} />
    </div>
  );
}
