import { ApiError, apiFetch, Button, Card, seriesColor, useSwr } from "@urbanflet/shared-ui";
import { useIrASeccion, useSeccionesDisponibles } from "../../navegacion";
import { NotaLimitacion } from "./comunes";
import { entero, pct, tonoVariacion, variacion } from "./formato";

// spec: specs/nivel-estrategico/nivel_estrategico.md §4 — Tablero Ejecutivo
// Consolidado (CU-E01). Un KPI headline por cada uno de los 8 dashboards
// estratégicos, cada tarjeta con un enlace "Ver detalle" que navega al panel
// correspondiente. Patrón Z: filas de tarjetas homogéneas, sin gráfico
// propio — es un índice de navegación, no un dashboard analítico.
const RECURSO = "/estrategico/tablero-ejecutivo";

const SIN_TARJETAS: TarjetaEjecutiva[] = [];

/**
 * Enlace secundario opcional al dashboard TÁCTICO del mismo dominio (spec §2:
 * "bajar del resumen al detalle departamental"). Solo se pinta si el rol del
 * actor ve esa sección — `gerencia`, por ejemplo, ve Auditoría y Plataforma
 * tácticos pero no Captación ni Mantenimiento tácticos, así que ahí el enlace
 * simplemente no aparece en vez de llevar a una pantalla en blanco.
 *
 * `rentabilidad` no tiene equivalente táctico: el margen por franja es un
 * cálculo nuevo de este nivel, no la consolidación de un panel táctico.
 */
const SECCION_TACTICA: Record<string, string | undefined> = {
  crecimiento: "tactico-captacion",
  confiabilidad: "tactico-despacho",
  "estado-costo-flota": "tactico-mantenimiento",
  capacidades: "tactico-plataforma",
  rentabilidad: undefined,
  "integridad-financiera": "tactico-conciliacion",
  "cumplimiento-normativo": "tactico-documentacion",
  gobernanza: "tactico-auditoria",
};

interface PuntoMiniTendencia {
  periodo: string;
  valor: number | null;
}

interface TarjetaEjecutiva {
  seccion: string;
  titulo: string;
  kpi: string;
  objetivo: string;
  valor: number | null;
  unidad: string;
  variacion_pct: number | null;
  tendencia: PuntoMiniTendencia[];
  disponible: boolean;
}

interface TableroEjecutivoOut {
  tarjetas: TarjetaEjecutiva[];
  metadata: { total: number; disponibles: number };
}

/**
 * Mini-tendencia (sparkline) de la tarjeta ejecutiva.
 *
 * Decisión de diseño: NO se reutiliza `TrendLineChart` acá. La spec §4 pide
 * explícitamente "KPI + mini-tendencia + enlace" dentro de una tarjeta de
 * índice — `TrendLineChart` trae ejes con ticks, grilla, tooltip y leyenda,
 * que en 90 px de alto compiten con el número que la tarjeta existe para
 * mostrar. Este SVG usa el MISMO color de serie 1 de la paleta validada
 * (`seriesColor(0)`, tokens `--chart-series-*`), así que no introduce color
 * nuevo fuera del sistema. Es la única visualización nueva de la Fase 4.
 */
function MiniTendencia({ puntos }: { puntos: PuntoMiniTendencia[] }) {
  const valores = puntos.map((p) => p.valor).filter((v): v is number => v != null);
  if (valores.length < 2) {
    return <div style={{ height: 40 }} aria-hidden="true" />;
  }
  const min = Math.min(...valores);
  const max = Math.max(...valores);
  const rango = max - min || 1;
  const ancho = 100;
  const alto = 40;
  const coords = valores.map((v, i) => {
    const x = (i / (valores.length - 1)) * ancho;
    const y = alto - ((v - min) / rango) * (alto - 6) - 3;
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  });
  return (
    <svg
      viewBox={`0 0 ${ancho} ${alto}`}
      preserveAspectRatio="none"
      style={{ width: "100%", height: 40, display: "block" }}
      role="img"
      aria-label={`Mini-tendencia de ${valores.length} periodos`}
    >
      <polyline points={coords.join(" ")} fill="none" stroke={seriesColor(0)} strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

function valorLegible(t: TarjetaEjecutiva): string {
  if (!t.disponible || t.valor == null) return "—";
  return t.unidad === "porcentaje" ? pct(t.valor) : entero(t.valor);
}

export function TableroEjecutivo() {
  const irASeccion = useIrASeccion();
  const disponibles = useSeccionesDisponibles();

  const { data, error: errorCarga } = useSwr<TableroEjecutivoOut>(RECURSO, () =>
    apiFetch<TableroEjecutivoOut>(RECURSO),
  );
  const error = errorCarga
    ? errorCarga instanceof ApiError
      ? errorCarga.message
      : "No se pudo cargar el tablero ejecutivo"
    : null;

  const tarjetas = data?.tarjetas ?? SIN_TARJETAS;
  const meta = data?.metadata;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
      <h2 style={{ margin: 0 }}>Tablero Ejecutivo Consolidado</h2>
      {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
          gap: "var(--space-4)",
          alignItems: "stretch",
        }}
      >
        {tarjetas.map((t) => {
          const idEstrategico = `estrategico-${t.seccion}`;
          const idTactico = SECCION_TACTICA[t.seccion];
          const tono = tonoVariacion(t.variacion_pct, { subirEsBueno: t.seccion !== "capacidades" });
          return (
            <Card key={t.seccion}>
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)", height: "100%" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: "var(--space-2)" }}>
                  <h3 style={{ margin: 0, fontSize: "var(--font-size-md)" }}>{t.titulo}</h3>
                  <span style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>{t.objetivo}</span>
                </div>
                <p
                  style={{
                    margin: 0,
                    fontSize: "var(--font-size-sm)",
                    fontWeight: 500,
                    color: "var(--color-text-muted)",
                    textTransform: "uppercase",
                    letterSpacing: "0.03em",
                  }}
                >
                  {t.kpi}
                </p>
                <p
                  style={{
                    margin: 0,
                    fontSize: "var(--font-size-2xl)",
                    fontWeight: 700,
                    lineHeight: 1.1,
                    fontVariantNumeric: "tabular-nums",
                    color: t.disponible ? "var(--color-text)" : "var(--color-text-muted)",
                  }}
                >
                  {valorLegible(t)}
                </p>
                <p
                  style={{
                    margin: 0,
                    fontSize: "var(--font-size-sm)",
                    color: tono === "exito" ? "var(--status-good)" : tono === "peligro" ? "var(--status-critical)" : "var(--color-text-muted)",
                  }}
                >
                  {t.variacion_pct == null ? "Sin variación comparable" : `${variacion(t.variacion_pct)} vs. periodo previo`}
                </p>
                <MiniTendencia puntos={t.tendencia} />
                <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap", marginTop: "auto" }}>
                  {disponibles.includes(idEstrategico) && (
                    <Button onClick={() => irASeccion(idEstrategico)}>Ver detalle</Button>
                  )}
                  {idTactico && disponibles.includes(idTactico) && (
                    <Button variant="secondary" onClick={() => irASeccion(idTactico)}>
                      Ver táctico
                    </Button>
                  )}
                </div>
                {!t.disponible && (
                  <NotaLimitacion>
                    Fuente sin datos publicados todavía — la tarjeta se muestra en "sin dato" en vez de
                    tumbar el tablero completo.
                  </NotaLimitacion>
                )}
              </div>
            </Card>
          );
        })}
      </div>

      {meta && (
        <NotaLimitacion>
          {meta.disponibles} de {meta.total} indicadores con dato publicado. Cada headline se calcula con
          el mismo servicio que sirve su dashboard de detalle, así que el número de esta tarjeta y el del
          panel no pueden divergir.
        </NotaLimitacion>
      )}
    </div>
  );
}
