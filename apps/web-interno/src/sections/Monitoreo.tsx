import {
  ActionBar,
  ApiError,
  apiFetch,
  Badge,
  Button,
  Card,
  DataTable,
  DetailPanel,
  KpiCard,
  KpiRow,
  TextField,
  TrendLineChart,
  fieldError,
  type ModoPanel,
} from "@urbanflet/shared-ui";
import { useEffect, useRef, useState } from "react";

interface SaludComponente {
  componente: "backend" | "mongo" | "redis" | "clickhouse" | "airflow";
  disponible: boolean;
  latencia_ms: number | null;
  estado: "bien" | "advertencia" | "critico";
}

interface Umbral {
  componente: SaludComponente["componente"];
  latencia_advertencia_ms: number;
  latencia_critica_ms: number;
}

interface IndicadorMongo {
  disponible: boolean;
  conexiones_activas: number | null;
  conexiones_disponibles: number | null;
  operaciones_totales: number | null;
  tamano_datos_mb: number | null;
  tamano_almacenamiento_mb: number | null;
  colecciones: number | null;
  indices: number | null;
  tiempo_actividad_seg: number | null;
}

interface IndicadorRedis {
  disponible: boolean;
  memoria_usada_mb: number | null;
  clientes_conectados: number | null;
  hit_rate_pct: number | null;
  tiempo_actividad_seg: number | null;
}

interface IndicadorClickhouse {
  disponible: boolean;
  consultas_activas: number | null;
  memoria_usada_mb: number | null;
  tiempo_actividad_seg: number | null;
}

interface Indicadores {
  mongo: IndicadorMongo;
  redis: IndicadorRedis;
  clickhouse: IndicadorClickhouse;
}

interface HistorialPunto {
  ts: string;
  componente: SaludComponente["componente"];
  latencia_ms: number | null;
  estado: SaludComponente["estado"];
}

const NOMBRE_COMPONENTE: Record<SaludComponente["componente"], string> = {
  backend: "Backend",
  mongo: "MongoDB",
  redis: "Redis",
  clickhouse: "ClickHouse",
  airflow: "Airflow",
};

const AUTO_REFRESCO_MS = 20_000;

const TONO_KPI: Record<SaludComponente["estado"], "exito" | "advertencia" | "peligro"> = {
  bien: "exito",
  advertencia: "advertencia",
  critico: "peligro",
};

const TONO_BADGE: Record<SaludComponente["estado"], "exito" | "advertencia" | "peligro"> = {
  bien: "exito",
  advertencia: "advertencia",
  critico: "peligro",
};

function formatoHora(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function pivotarHistorial(puntos: HistorialPunto[]): Array<Record<string, string | number | null>> {
  const porTs = new Map<string, Record<string, string | number | null>>();
  for (const p of puntos) {
    const fila = porTs.get(p.ts) ?? { ts: formatoHora(p.ts) };
    fila[p.componente] = p.latencia_ms;
    porTs.set(p.ts, fila);
  }
  return Array.from(porTs.values());
}

export function SeccionMonitoreo() {
  const [salud, setSalud] = useState<SaludComponente[]>([]);
  const [umbrales, setUmbrales] = useState<Umbral[]>([]);
  const [indicadores, setIndicadores] = useState<Indicadores | null>(null);
  const [historial, setHistorial] = useState<HistorialPunto[]>([]);
  const [seleccionado, setSeleccionado] = useState<Umbral | null>(null);
  const [modo, setModo] = useState<ModoPanel>("consulta");
  const [advertenciaMs, setAdvertenciaMs] = useState("");
  const [criticaMs, setCriticaMs] = useState("");
  const [cargandoPanel, setCargandoPanel] = useState(false);
  const [cargandoSalud, setCargandoSalud] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [ultimaConsulta, setUltimaConsulta] = useState<Date | null>(null);
  const [autoRefrescoActivo, setAutoRefrescoActivo] = useState(true);
  const autoRefrescoRef = useRef(autoRefrescoActivo);
  autoRefrescoRef.current = autoRefrescoActivo;

  const mensajeGeneral =
    error instanceof ApiError ? error.message : error ? "No se pudo completar la operación" : null;

  const cargar = async () => {
    setCargandoSalud(true);
    setError(null);
    try {
      const [saludResp, umbralesResp, indicadoresResp, historialResp] = await Promise.all([
        apiFetch<SaludComponente[]>("/sistema/salud"),
        apiFetch<Umbral[]>("/sistema/umbrales-monitoreo"),
        apiFetch<Indicadores>("/sistema/indicadores"),
        apiFetch<HistorialPunto[]>("/sistema/historial-latencia?horas=1"),
      ]);
      setSalud(saludResp);
      setUmbrales(umbralesResp);
      setIndicadores(indicadoresResp);
      setHistorial(historialResp);
      setUltimaConsulta(new Date());
    } catch (e) {
      setError(e);
    } finally {
      setCargandoSalud(false);
    }
  };

  useEffect(() => {
    cargar();
  }, []);

  useEffect(() => {
    const intervalo = setInterval(() => {
      if (autoRefrescoRef.current) cargar();
    }, AUTO_REFRESCO_MS);
    return () => clearInterval(intervalo);
  }, []);

  const abrirDetalle = (u: Umbral) => {
    setSeleccionado(u);
    setModo("edicion");
    setAdvertenciaMs(String(u.latencia_advertencia_ms));
    setCriticaMs(String(u.latencia_critica_ms));
    setError(null);
  };

  const guardar = async () => {
    if (!seleccionado) return;
    setError(null);
    setCargandoPanel(true);
    try {
      await apiFetch(`/sistema/umbrales-monitoreo/${seleccionado.componente}`, {
        method: "PUT",
        body: { latencia_advertencia_ms: Number(advertenciaMs), latencia_critica_ms: Number(criticaMs) },
      });
      setSeleccionado(null);
      setModo("consulta");
      await cargar();
    } catch (e) {
      setError(e);
    } finally {
      setCargandoPanel(false);
    }
  };

  const aceptarInvalido =
    !advertenciaMs || !criticaMs || Number(advertenciaMs) <= 0 || Number(criticaMs) <= Number(advertenciaMs);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <Card>
        <h2 style={{ marginTop: 0, fontSize: "var(--font-size-lg)" }}>Monitoreo del sistema</h2>
        <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
          Estado de infraestructura (backend, las 3 bases de datos y Airflow) evaluado bajo demanda — no hay
          vigilancia continua ni alerta push automática en este entorno; los umbrales de abajo solo colorean la
          tarjeta correspondiente en el momento de la consulta. El panel se actualiza solo cada 20 segundos; puedes
          pausarlo si estás inspeccionando un valor puntual.
        </p>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
          {ultimaConsulta && (
            <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)", margin: 0 }}>
              Última consulta: {ultimaConsulta.toLocaleString()}
            </p>
          )}
          <div style={{ minWidth: 220 }}>
            <Button variant="secondary" onClick={() => setAutoRefrescoActivo((a) => !a)}>
              {autoRefrescoActivo ? "Pausar actualización automática" : "Reanudar actualización automática (20s)"}
            </Button>
          </div>
        </div>
      </Card>

      {mensajeGeneral && (
        <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{mensajeGeneral}</p>
      )}

      <Card>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-3)" }}>
          <h3 style={{ margin: 0, fontSize: "var(--font-size-md)" }}>Estado actual</h3>
          <div style={{ minWidth: 140 }}>
            <Button variant="secondary" onClick={cargar} loading={cargandoSalud}>Actualizar</Button>
          </div>
        </div>
        <KpiRow>
          {salud.map((c) => (
            <KpiCard
              key={c.componente}
              etiqueta={NOMBRE_COMPONENTE[c.componente]}
              descripcion="Tiempo de respuesta al último chequeo — más alto es peor."
              valor={c.disponible && c.latencia_ms !== null ? `${c.latencia_ms} ms` : "No disponible"}
              tono={TONO_KPI[c.estado]}
            />
          ))}
        </KpiRow>
      </Card>

      <Card>
        <h3 style={{ marginTop: 0, fontSize: "var(--font-size-md)" }}>Indicadores adicionales</h3>
        <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
          Métricas reales de cada motor (conexiones, memoria, actividad) vía los mismos comandos que usan sus
          propios clientes de administración — sin Airflow por ahora.
        </p>
        <KpiRow>
          <KpiCard
            etiqueta="Mongo — conexiones activas"
            descripcion="Conexiones abiertas a la base de datos operativa ahora mismo."
            valor={indicadores?.mongo.disponible ? String(indicadores.mongo.conexiones_activas ?? "—") : "No disponible"}
          />
          <KpiCard
            etiqueta="Mongo — tamaño de datos"
            descripcion="Espacio ocupado por los datos almacenados."
            valor={indicadores?.mongo.disponible ? `${indicadores.mongo.tamano_datos_mb ?? "—"} MB` : "No disponible"}
          />
          <KpiCard
            etiqueta="Redis — memoria usada"
            descripcion="Memoria RAM que usa el caché (posiciones, sesiones, colas) ahora mismo."
            valor={indicadores?.redis.disponible ? `${indicadores.redis.memoria_usada_mb ?? "—"} MB` : "No disponible"}
          />
          <KpiCard
            etiqueta="Redis — % de aciertos de caché"
            descripcion="% de lecturas del caché que encontraron el dato ahí, sin ir a la base de datos."
            valor={indicadores?.redis.disponible ? `${indicadores.redis.hit_rate_pct ?? "—"}%` : "No disponible"}
          />
          <KpiCard
            etiqueta="ClickHouse — consultas activas"
            descripcion="Consultas analíticas en ejecución ahora mismo."
            valor={indicadores?.clickhouse.disponible ? String(indicadores.clickhouse.consultas_activas ?? "—") : "No disponible"}
          />
          <KpiCard
            etiqueta="ClickHouse — memoria usada"
            descripcion="Memoria RAM que usa el motor analítico ahora mismo."
            valor={indicadores?.clickhouse.disponible ? `${indicadores.clickhouse.memoria_usada_mb ?? "—"} MB` : "No disponible"}
          />
        </KpiRow>
      </Card>

      <Card>
        <h3 style={{ marginTop: 0, fontSize: "var(--font-size-md)" }}>Tendencia de latencia (última hora)</h3>
        <TrendLineChart
          datos={pivotarHistorial(historial)}
          eje="ts"
          series={(["backend", "mongo", "redis", "clickhouse", "airflow"] as const).map((c) => ({
            key: c,
            label: NOMBRE_COMPONENTE[c],
          }))}
          formatoValor={(v) => `${v} ms`}
          vacio="Todavía no hay suficiente histórico — se acumula con cada consulta real de este panel."
        />
      </Card>

      <Card>
        {/* "Nuevo"/"Eliminar"/"Buscar" quitados (segunda pasada, punto 1):
            los 5 componentes monitoreados son fijos y la lista no pagina --
            ningún rol tiene un uso real para ninguno de los tres acá. */}
        <ActionBar actualizar={{ onClick: () => cargar() }} salir={{ onClick: () => setSeleccionado(null) }} />
        <div style={{ marginTop: "var(--space-3)" }}>
          <DataTable
            rows={umbrales}
            keyField={(u) => u.componente}
            vacio="Sin umbrales configurados."
            columns={[
              { header: "Componente", render: (u) => NOMBRE_COMPONENTE[u.componente] },
              { header: "Advertencia (ms)", render: (u) => u.latencia_advertencia_ms },
              { header: "Crítico (ms)", render: (u) => u.latencia_critica_ms },
              {
                header: "Estado actual",
                render: (u) => {
                  const s = salud.find((c) => c.componente === u.componente);
                  return s ? <Badge texto={s.estado.toUpperCase()} tono={TONO_BADGE[s.estado]} /> : "—";
                },
              },
              { header: "Detalle", render: (u) => <Button variant="secondary" onClick={() => abrirDetalle(u)}>Editar</Button> },
            ]}
          />
        </div>
      </Card>

      {seleccionado && modo === "edicion" && (
        <DetailPanel
          titulo={`Umbral — ${NOMBRE_COMPONENTE[seleccionado.componente]}`}
          modo="edicion"
          onSalir={() => { setSeleccionado(null); setModo("consulta"); }}
          onAceptar={guardar}
          aceptarLabel="Guardar"
          aceptarDisabled={aceptarInvalido}
          aceptarLoading={cargandoPanel}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            {mensajeGeneral && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{mensajeGeneral}</p>}
            <TextField
              label="Latencia de advertencia (ms)"
              type="number"
              min={1}
              max={60000}
              value={advertenciaMs}
              onChange={(e) => setAdvertenciaMs(e.target.value)}
              error={fieldError(error, "latencia_advertencia_ms")}
            />
            <TextField
              label="Latencia crítica (ms)"
              type="number"
              min={1}
              max={60000}
              value={criticaMs}
              onChange={(e) => setCriticaMs(e.target.value)}
              error={fieldError(error, "latencia_critica_ms")}
            />
          </div>
        </DetailPanel>
      )}
    </div>
  );
}
