import {
  ActionBar,
  ApiError,
  apiFetch,
  Badge,
  Button,
  Card,
  DataTable,
  DetailField,
  DetailPanel,
  invalidateSwrPrefix,
  Pagination,
  Select,
  TextArea,
  TextField,
  useSwr,
} from "@urbanflet/shared-ui";
import { useMemo, useState } from "react";

const RECURSO_EVENTOS_AUDITORIA = "/auditoria/eventos";
const RECURSO_RENOVACIONES = "/cumplimiento/documentos/renovaciones-pendientes";

interface ResultadoControl {
  revisados: number;
  por_vencer_notificados: number;
  vencidos_nuevos: number;
}

interface RenovacionPendiente {
  documento_id: string;
  tipo: string;
  propietario_tipo: string;
  propietario_id: string;
  propietario_nombre: string | null;
  fecha_vencimiento_actual: string | null;
  fecha_vencimiento_propuesta: string;
}

interface EventoAuditoria {
  evento_id: number;
  ts: string;
  actor_id: string | null;
  rol: string | null;
  accion: string;
  entidad: string;
  entidad_id: string | null;
  resultado: string;
  ip: string | null;
  dispositivo: string | null;
}

interface EventosPage {
  items: EventoAuditoria[];
  total: number;
}

// CU-O17/CU-O18: bitácora de auditoría (GET /auditoria/eventos, ya con RBAC
// restringido a supervisor_cumplimiento/admin_plataforma/gerencia en el
// backend) y las alertas de seguridad — que no viven en un canal aparte, son
// el mismo evento ACCESO_DENEGADO ya escrito en la bitácora cuando el RBAC
// deniega un intento (ver core/rbac.py) — así que se muestran como un badge
// que cuenta esos eventos en las últimas 24h, sin inventar infraestructura
// de notificaciones en vivo nueva para esto.
function SeccionBitacoraAuditoria() {
  const [actorId, setActorId] = useState("");
  const [entidad, setEntidad] = useState("");
  const [accion, setAccion] = useState("");
  const [resultadoFiltro, setResultadoFiltro] = useState("");
  const [pagina, setPagina] = useState(0);
  const tamanioPagina = 20;

  const claveConsulta = (() => {
    const params = new URLSearchParams({ pagina: String(pagina + 1), tamanio_pagina: String(tamanioPagina) });
    if (actorId) params.set("actor_id", actorId);
    if (entidad) params.set("entidad", entidad);
    if (accion) params.set("accion", accion);
    if (resultadoFiltro) params.set("resultado", resultadoFiltro);
    return `${RECURSO_EVENTOS_AUDITORIA}?${params.toString()}`;
  })();
  const { data, error: errorCarga } = useSwr<EventosPage>(claveConsulta, () => apiFetch<EventosPage>(claveConsulta));
  const eventos = data?.items ?? [];
  const total = data?.total ?? 0;
  const error = errorCarga ? (errorCarga instanceof ApiError ? errorCarga.message : "No se pudo cargar la bitácora") : null;

  // "desde" se redondea a baldes de 5 minutos -- si se recalculara con
  // `Date.now()` en cada render, la key cambiaría en cada render (distinto
  // "ahora - 24h" hasta el milisegundo) y el hook nunca podría servir desde
  // caché ni evitar un fetch nuevo en cada repintado. El balde de 5 minutos
  // conserva el propósito (ventana de "últimas 24h", sin precisión real de
  // milisegundo) mientras mantiene la key estable entre renders.
  const baldeMs = 5 * 60 * 1000;
  const desdeBalde = Math.floor((Date.now() - 24 * 60 * 60 * 1000) / baldeMs) * baldeMs;
  const claveAlertas = `${RECURSO_EVENTOS_AUDITORIA}?accion=ACCESO_DENEGADO&desde=${encodeURIComponent(
    new Date(desdeBalde).toISOString(),
  )}&tamanio_pagina=1`;
  const { data: datosAlertas } = useSwr<EventosPage>(claveAlertas, () => apiFetch<EventosPage>(claveAlertas));
  const alertas24h = datosAlertas?.total ?? 0;

  return (
    <Card>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-3)" }}>
        <h2 style={{ margin: 0, fontSize: "var(--font-size-lg)" }}>Bitácora de auditoría</h2>
        <Badge
          texto={`${alertas24h} alertas de seguridad (24h)`}
          tono={alertas24h > 0 ? "peligro" : "neutral"}
        />
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-3)", marginBottom: "var(--space-3)" }}>
        <div style={{ minWidth: 180 }}>
          <TextField
            label="Actor (id)"
            value={actorId}
            onChange={(e) => {
              setActorId(e.target.value);
              setPagina(0);
            }}
          />
        </div>
        <div style={{ minWidth: 160 }}>
          <TextField
            label="Entidad"
            value={entidad}
            onChange={(e) => {
              setEntidad(e.target.value);
              setPagina(0);
            }}
          />
        </div>
        <div style={{ minWidth: 200 }}>
          <TextField
            label="Acción"
            value={accion}
            onChange={(e) => {
              setAccion(e.target.value);
              setPagina(0);
            }}
          />
        </div>
        <div style={{ minWidth: 160 }}>
          <Select
            label="Resultado"
            value={resultadoFiltro}
            onChange={(e) => {
              setResultadoFiltro(e.target.value);
              setPagina(0);
            }}
            options={[
              { value: "", label: "Todos" },
              { value: "OK", label: "OK" },
              { value: "DENEGADO", label: "Denegado" },
              { value: "ERROR", label: "Error" },
            ]}
          />
        </div>
      </div>
      {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
      <DataTable
        rows={eventos}
        keyField={(e) => String(e.evento_id)}
        vacio="No hay eventos con estos filtros."
        columns={[
          { header: "Fecha", render: (e) => new Date(e.ts).toLocaleString() },
          { header: "Actor", render: (e) => e.actor_id ?? "—" },
          { header: "Rol", render: (e) => e.rol ?? "—" },
          { header: "Acción", render: (e) => e.accion },
          { header: "Entidad", render: (e) => `${e.entidad}${e.entidad_id ? ` (${e.entidad_id.slice(0, 8)}…)` : ""}` },
          {
            header: "Resultado",
            render: (e) => (
              <Badge texto={e.resultado} tono={e.resultado === "OK" ? "exito" : e.resultado === "DENEGADO" ? "peligro" : "advertencia"} />
            ),
          },
        ]}
      />
      <Pagination page={pagina} pageSize={tamanioPagina} total={total} onPageChange={setPagina} />
    </Card>
  );
}

// Mismo patrón WorkPanel del resto de web-interno (Solicitudes/
// Mantenimiento/Finanzas/Flota): búsqueda + lista paginada + botonera fija +
// detalle. GET /documentos/renovaciones-pendientes no pagina ni filtra en
// el servidor (lista corta por naturaleza — documentos vencidos o por
// vencer), así que la búsqueda/paginación son sobre el snapshot cargado en
// el cliente. A diferencia de la versión anterior, "Observar" ya no manda
// un motivo hardcodeado ("Documento observado desde el panel interno") —
// el supervisor lo escribe, igual que en Solicitudes.
function SeccionRenovaciones({ refreshSignal }: { refreshSignal: number }) {
  const [errorAccion, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  const [textoInput, setTextoInput] = useState("");
  const [filtroTexto, setFiltroTexto] = useState("");
  const [filtroTipo, setFiltroTipo] = useState("");
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(20);

  const [seleccionada, setSeleccionada] = useState<RenovacionPendiente | null>(null);
  const [decision, setDecision] = useState<"APROBAR" | "OBSERVAR">("APROBAR");
  const [motivo, setMotivo] = useState("");

  // `refreshSignal` (incrementado por el padre tras "Ejecutar control de
  // vigencia") se incluye en la key a propósito: fuerza una key nueva (sin
  // caché todavía) que dispara un fetch fresco, mismo efecto que el
  // `useEffect([refreshSignal])` de antes, pero conservando el caché
  // stale-while-revalidate para una visita normal de la sección (donde
  // `refreshSignal` vuelve a su valor inicial en cada montaje).
  const claveConsulta = `${RECURSO_RENOVACIONES}?refresh=${refreshSignal}`;
  const { data: pendientes = [], error: errorCarga, refetch: refetchPendientes } = useSwr<RenovacionPendiente[]>(
    claveConsulta,
    () => apiFetch<RenovacionPendiente[]>(RECURSO_RENOVACIONES),
  );
  const error =
    errorAccion ??
    (errorCarga ? (errorCarga instanceof ApiError ? errorCarga.message : "No se pudieron cargar las renovaciones") : null);

  const tiposDisponibles = useMemo(() => Array.from(new Set(pendientes.map((p) => p.tipo))).sort(), [pendientes]);

  const filtradas = useMemo(() => {
    const texto = filtroTexto.trim().toLowerCase();
    return pendientes.filter((p) => {
      if (filtroTipo && p.tipo !== filtroTipo) return false;
      if (!texto) return true;
      return (p.propietario_nombre ?? "").toLowerCase().includes(texto) || p.propietario_id.toLowerCase().includes(texto);
    });
  }, [pendientes, filtroTexto, filtroTipo]);

  const paginadas = filtradas.slice(page * pageSize, (page + 1) * pageSize);

  const buscar = () => {
    setFiltroTexto(textoInput.trim());
    setPage(0);
  };

  const limpiarBusqueda = () => {
    setTextoInput("");
    setFiltroTexto("");
    setFiltroTipo("");
    setPage(0);
    setSeleccionada(null);
  };

  const abrirDetalle = (p: RenovacionPendiente) => {
    setSeleccionada(p);
    setDecision("APROBAR");
    setMotivo("");
    setError(null);
  };

  const decidir = async () => {
    if (!seleccionada) return;
    setError(null);
    setCargando(true);
    try {
      await apiFetch(`/cumplimiento/documentos/${seleccionada.documento_id}/renovacion/verificacion`, {
        method: "POST",
        body: { aprobar: decision === "APROBAR", motivo: decision === "OBSERVAR" ? motivo : undefined },
      });
      setSeleccionada(null);
      setMotivo("");
      invalidateSwrPrefix(RECURSO_RENOVACIONES);
      await refetchPendientes();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo verificar la renovación");
    } finally {
      setCargando(false);
    }
  };

  return (
    <>
      <Card>
        <h2 style={{ marginTop: 0, fontSize: "var(--font-size-lg)" }}>Buscar renovaciones pendientes</h2>
        <div style={{ display: "flex", gap: "var(--space-3)", flexWrap: "wrap", alignItems: "flex-end" }}>
          <div style={{ minWidth: 220 }}>
            <TextField
              label="Propietario"
              value={textoInput}
              onChange={(e) => setTextoInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && buscar()}
            />
          </div>
          <div style={{ minWidth: 200 }}>
            <Select
              label="Tipo de documento"
              value={filtroTipo}
              onChange={(e) => {
                setFiltroTipo(e.target.value);
                setPage(0);
              }}
              options={[{ value: "", label: "Todos" }, ...tiposDisponibles.map((t) => ({ value: t, label: t }))]}
            />
          </div>
        </div>
      </Card>

      <ActionBar
        nuevo={{
          onClick: () => {},
          disabled: true,
          title: "No aplica: las renovaciones las suben los propios conductores/propietarios, no el personal interno.",
        }}
        actualizar={{ onClick: () => refetchPendientes() }}
        eliminar={{
          onClick: () => {},
          disabled: true,
          title: "No aplica: las renovaciones no se eliminan, solo se aprueban u observan.",
        }}
        buscar={{ onClick: buscar }}
        salir={{ onClick: limpiarBusqueda }}
      />

      <Card>
        {error && !seleccionada && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
        <DataTable
          rows={paginadas}
          keyField={(p) => p.documento_id}
          vacio="No hay renovaciones pendientes con este filtro."
          columns={[
            { header: "Tipo", render: (p) => p.tipo },
            {
              header: "Propietario",
              render: (p) =>
                `${p.propietario_tipo === "CONDUCTOR" ? "Conductor" : "Vehículo"} · ${
                  p.propietario_nombre ?? `sin datos (${p.propietario_id.slice(0, 8)}…)`
                }`,
            },
            { header: "Vence hoy", render: (p) => p.fecha_vencimiento_actual ?? "—" },
            { header: "Nueva fecha", render: (p) => p.fecha_vencimiento_propuesta },
            {
              header: "Detalle",
              render: (p) => (
                <Button variant="secondary" onClick={() => abrirDetalle(p)}>
                  Ver
                </Button>
              ),
            },
          ]}
        />
        <Pagination
          page={page}
          pageSize={pageSize}
          total={filtradas.length}
          onPageChange={setPage}
          onPageSizeChange={(n) => {
            setPageSize(n);
            setPage(0);
          }}
        />
      </Card>

      {seleccionada && (
        <DetailPanel
          titulo={`Renovación — ${seleccionada.propietario_nombre ?? seleccionada.propietario_id.slice(0, 8) + "…"}`}
          modo="edicion"
          onSalir={() => setSeleccionada(null)}
          onAceptar={decidir}
          aceptarLabel="Aceptar decisión"
          aceptarDisabled={decision === "OBSERVAR" && !motivo.trim()}
          aceptarLoading={cargando}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
            {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "var(--space-3)" }}>
              <DetailField label="Tipo de documento" value={seleccionada.tipo} />
              <DetailField
                label="Propietario"
                value={`${seleccionada.propietario_tipo === "CONDUCTOR" ? "Conductor" : "Vehículo"} · ${
                  seleccionada.propietario_nombre ?? `sin datos (${seleccionada.propietario_id})`
                }`}
              />
              <DetailField label="Vence hoy" value={seleccionada.fecha_vencimiento_actual ?? "—"} />
              <DetailField label="Nueva fecha propuesta" value={seleccionada.fecha_vencimiento_propuesta} />
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", borderTop: "1px solid var(--color-border)", paddingTop: "var(--space-3)" }}>
              <Select
                label="Decisión"
                value={decision}
                onChange={(e) => setDecision(e.target.value as typeof decision)}
                options={[
                  { value: "APROBAR", label: "Aprobar" },
                  { value: "OBSERVAR", label: "Observar" },
                ]}
              />
              {decision === "OBSERVAR" && (
                <TextArea label="Motivo (obligatorio)" value={motivo} onChange={(e) => setMotivo(e.target.value)} />
              )}
            </div>
          </div>
        </DetailPanel>
      )}
    </>
  );
}

export function SeccionCumplimiento() {
  const [resultado, setResultado] = useState<ResultadoControl | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);
  const [refreshSignal, setRefreshSignal] = useState(0);

  const ejecutarControl = async () => {
    setError(null);
    setCargando(true);
    try {
      const r = await apiFetch<ResultadoControl>("/cumplimiento/control-vigencia", { method: "POST" });
      setResultado(r);
      // El control de vigencia puede generar/actualizar renovaciones
      // pendientes (nuevos vencidos, notificaciones de por-vencer) — se
      // refresca la lista de abajo en vez de dejarla desactualizada.
      setRefreshSignal((n) => n + 1);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo ejecutar el control de vigencia");
    } finally {
      setCargando(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <Card>
        <h2 style={{ marginTop: 0, fontSize: "var(--font-size-lg)" }}>Control de vigencia documental</h2>
        <p style={{ color: "var(--color-text-muted)" }}>
          En producción corre automáticamente a las 06:00. Este botón lo dispara bajo demanda.
        </p>
        {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
        <Button onClick={ejecutarControl} loading={cargando}>
          Ejecutar control de vigencia
        </Button>
        {resultado && (
          <p style={{ marginTop: "var(--space-3)", color: "var(--color-text-muted)" }}>
            Revisados: {resultado.revisados} · Por vencer notificados: {resultado.por_vencer_notificados} · Vencidos
            nuevos: {resultado.vencidos_nuevos}
          </p>
        )}
      </Card>

      <SeccionRenovaciones refreshSignal={refreshSignal} />

      <SeccionBitacoraAuditoria />
    </div>
  );
}
