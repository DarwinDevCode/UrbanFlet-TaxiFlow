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
  type ModoPanel,
} from "@urbanflet/shared-ui";
import { useState } from "react";

const RECURSO_SOLICITUDES = "/captacion/solicitudes";

interface Solicitud {
  id: string;
  usuario_id: string;
  usuario_nombre: string | null;
  cedula: string;
  estado: string;
  fecha_envio: string | null;
  fecha_decision: string | null;
  revision_reforzada: boolean;
  motivo_rechazo: string | null;
}

interface SolicitudListOut {
  items: Solicitud[];
  total: number;
}

const tonoPorEstado: Record<string, "neutral" | "exito" | "advertencia" | "peligro"> = {
  ENVIADA: "neutral",
  EN_VERIFICACION: "advertencia",
  OBSERVADA: "advertencia",
  APROBADA: "exito",
  RECHAZADA: "peligro",
};

// Convención de "Salir" para esta pantalla (y las otras dos del mismo
// patrón): en la barra fija de acciones, "Salir" limpia los criterios de
// búsqueda y vuelve a la lista por defecto (sin selección). Dentro del
// panel de detalle, "Salir" cierra el panel sin aplicar cambios.
export function SeccionSolicitudes() {
  const [filtroEstado, setFiltroEstado] = useState("");
  const [filtroCedula, setFiltroCedula] = useState("");
  const [cedulaInput, setCedulaInput] = useState("");
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(20);

  const [seleccionada, setSeleccionada] = useState<Solicitud | null>(null);
  const [modo, setModo] = useState<ModoPanel>("consulta");
  const [decision, setDecision] = useState<"APROBADA" | "RECHAZADA" | "OBSERVADA">("APROBADA");
  const [motivo, setMotivo] = useState("");
  const [errorAccion, setErrorAccion] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);
  const [tomando, setTomando] = useState(false);

  // Caché stale-while-revalidate (ver `swrCache.ts`): al volver a esta
  // sección con la misma combinación de filtros/página ya visitada en la
  // sesión, la lista se muestra de inmediato desde caché mientras se
  // revalida en segundo plano contra el backend.
  const claveConsulta = (() => {
    const params = new URLSearchParams();
    if (filtroEstado) params.set("estado", filtroEstado);
    if (filtroCedula) params.set("cedula", filtroCedula);
    params.set("limit", String(pageSize));
    params.set("offset", String(page * pageSize));
    return `${RECURSO_SOLICITUDES}?${params.toString()}`;
  })();
  const { data, error: errorCarga, refetch } = useSwr<SolicitudListOut>(claveConsulta, () =>
    apiFetch<SolicitudListOut>(claveConsulta),
  );
  const solicitudes = data?.items ?? [];
  const total = data?.total ?? 0;
  const error =
    errorAccion ??
    (errorCarga ? (errorCarga instanceof ApiError ? errorCarga.message : "No se pudieron cargar las solicitudes") : null);

  const buscar = () => {
    setFiltroCedula(cedulaInput.trim());
    setPage(0);
  };

  const limpiarBusqueda = () => {
    setFiltroEstado("");
    setCedulaInput("");
    setFiltroCedula("");
    setPage(0);
    setSeleccionada(null);
  };

  const abrirDetalle = (s: Solicitud) => {
    setSeleccionada(s);
    setModo(s.estado === "EN_VERIFICACION" || s.estado === "OBSERVADA" ? "edicion" : "consulta");
    setDecision("APROBADA");
    setMotivo("");
    setErrorAccion(null);
  };

  const tomar = async () => {
    if (!seleccionada) return;
    setErrorAccion(null);
    setTomando(true);
    try {
      const actualizada = await apiFetch<Solicitud>(`/captacion/solicitudes/${seleccionada.id}/tomar`, {
        method: "POST",
      });
      setSeleccionada(actualizada);
      setModo("edicion");
      invalidateSwrPrefix(RECURSO_SOLICITUDES);
      await refetch();
    } catch (e) {
      setErrorAccion(e instanceof ApiError ? e.message : "No se pudo tomar la solicitud");
    } finally {
      setTomando(false);
    }
  };

  const decidir = async () => {
    if (!seleccionada) return;
    setErrorAccion(null);
    setCargando(true);
    try {
      await apiFetch(`/captacion/solicitudes/${seleccionada.id}/decision`, {
        method: "POST",
        body: { decision, motivo: motivo || undefined },
      });
      setSeleccionada(null);
      setMotivo("");
      invalidateSwrPrefix(RECURSO_SOLICITUDES);
      await refetch();
    } catch (e) {
      setErrorAccion(e instanceof ApiError ? e.message : "No se pudo registrar la decisión");
    } finally {
      setCargando(false);
    }
  };

  const puedeDecidir = seleccionada && (seleccionada.estado === "EN_VERIFICACION" || seleccionada.estado === "OBSERVADA");
  const puedeTomar = seleccionada && seleccionada.estado === "ENVIADA";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <Card>
        <h2 style={{ marginTop: 0, fontSize: "var(--font-size-lg)" }}>Buscar solicitudes de socios conductores</h2>
        <div style={{ display: "flex", gap: "var(--space-3)", flexWrap: "wrap", alignItems: "flex-end" }}>
          <div style={{ minWidth: 220 }}>
            <Select
              label="Estado"
              value={filtroEstado}
              onChange={(e) => {
                setFiltroEstado(e.target.value);
                setPage(0);
              }}
              options={[
                { value: "", label: "Todas" },
                { value: "ENVIADA", label: "Enviadas" },
                { value: "EN_VERIFICACION", label: "En verificación" },
                { value: "OBSERVADA", label: "Observadas" },
                { value: "APROBADA", label: "Aprobadas" },
                { value: "RECHAZADA", label: "Rechazadas" },
              ]}
            />
          </div>
          <div style={{ minWidth: 220 }}>
            <TextField
              label="Cédula"
              value={cedulaInput}
              onChange={(e) => setCedulaInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && buscar()}
            />
          </div>
        </div>
      </Card>

      <ActionBar
        nuevo={{
          onClick: () => {},
          disabled: true,
          title: "No aplica: las solicitudes las crean los propios postulantes, no el personal interno.",
        }}
        actualizar={{ onClick: () => refetch() }}
        eliminar={{
          onClick: () => {},
          disabled: true,
          title: "No aplica: las solicitudes no se eliminan, solo cambian de estado.",
        }}
        buscar={{ onClick: buscar }}
        salir={{ onClick: limpiarBusqueda }}
      />

      <Card>
        {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}

        <DataTable
          rows={solicitudes}
          keyField={(s) => s.id}
          vacio="No hay solicitudes con este filtro."
          columns={[
            { header: "Cédula", render: (s) => s.cedula },
            {
              header: "Estado",
              render: (s) => (
                <>
                  <Badge texto={s.estado} tono={tonoPorEstado[s.estado] ?? "neutral"} />
                  {s.revision_reforzada && (
                    <span style={{ marginLeft: "var(--space-2)" }}>
                      <Badge texto="Revisión reforzada" tono="advertencia" />
                    </span>
                  )}
                </>
              ),
            },
            { header: "Enviada", render: (s) => (s.fecha_envio ? new Date(s.fecha_envio).toLocaleDateString() : "—") },
            {
              header: "Detalle",
              render: (s) => (
                <Button variant="secondary" onClick={() => abrirDetalle(s)}>
                  Ver
                </Button>
              ),
            },
          ]}
        />
        <Pagination page={page} pageSize={pageSize} total={total} onPageChange={setPage} onPageSizeChange={(n) => { setPageSize(n); setPage(0); }} />
      </Card>

      {seleccionada && (
        <DetailPanel
          titulo={`Solicitud — cédula ${seleccionada.cedula}`}
          modo={modo}
          onSalir={() => setSeleccionada(null)}
          accionesExtra={
            <>
              {puedeTomar && (
                <div style={{ minWidth: 140 }}>
                  <Button variant="secondary" onClick={tomar} loading={tomando}>
                    Tomar
                  </Button>
                </div>
              )}
            </>
          }
          onAceptar={puedeDecidir ? decidir : undefined}
          aceptarLabel="Aceptar decisión"
          aceptarDisabled={decision !== "APROBADA" && !motivo}
          aceptarLoading={cargando}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
            {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "var(--space-3)" }}>
              <DetailField
                label="Postulante"
                value={
                  seleccionada.usuario_nombre ?? (
                    <span style={{ color: "var(--color-text-muted)", fontStyle: "italic" }}>
                      Sin nombre registrado ({seleccionada.usuario_id})
                    </span>
                  )
                }
              />
              <DetailField label="Cédula" value={seleccionada.cedula} />
              <DetailField label="Estado" value={<Badge texto={seleccionada.estado} tono={tonoPorEstado[seleccionada.estado] ?? "neutral"} />} />
              <DetailField label="Revisión reforzada" value={seleccionada.revision_reforzada ? "Sí" : "No"} />
              <DetailField label="Fecha de envío" value={seleccionada.fecha_envio ? new Date(seleccionada.fecha_envio).toLocaleString() : "—"} />
              <DetailField label="Fecha de decisión" value={seleccionada.fecha_decision ? new Date(seleccionada.fecha_decision).toLocaleString() : "—"} />
              <DetailField label="Motivo de rechazo" value={seleccionada.motivo_rechazo ?? "—"} />
            </div>

            {puedeDecidir && (
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", borderTop: "1px solid var(--color-border)", paddingTop: "var(--space-3)" }}>
                <Select
                  label="Decisión"
                  value={decision}
                  onChange={(e) => setDecision(e.target.value as typeof decision)}
                  options={[
                    { value: "APROBADA", label: "Aprobar" },
                    { value: "RECHAZADA", label: "Rechazar" },
                    { value: "OBSERVADA", label: "Observar" },
                  ]}
                />
                {decision !== "APROBADA" && (
                  <TextArea label="Motivo (obligatorio)" value={motivo} onChange={(e) => setMotivo(e.target.value)} />
                )}
              </div>
            )}
          </div>
        </DetailPanel>
      )}
    </div>
  );
}
