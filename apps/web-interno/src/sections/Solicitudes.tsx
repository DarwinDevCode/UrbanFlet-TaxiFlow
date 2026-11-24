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
  EvidenciaImagen,
  invalidateSwrPrefix,
  nombreTipoDocumento,
  Pagination,
  Riel,
  Select,
  TextArea,
  TextField,
  trayectoSolicitud,
  useSwr,
  type ModoPanel,
} from "@urbanflet/shared-ui";
import { useState } from "react";

const RECURSO_SOLICITUDES = "/captacion/solicitudes";

interface VehiculoSolicitud {
  placa: string;
  marca: string;
  modelo: string;
  anio: number;
  color: string;
  capacidad: number;
}

interface Solicitud {
  id: string;
  usuario_id: string;
  usuario_nombre: string | null;
  cedula: string;
  // Ronda "corrección acotada por estado": el backend nunca los había
  // expuesto por API pese a pedirse al crear la solicitud -- sin esto, ni
  // esta pantalla podía mostrarlos, ni había nada que corregir.
  licencia_numero: string;
  vehiculo: VehiculoSolicitud;
  estado: string;
  fecha_envio: string | null;
  fecha_decision: string | null;
  revision_reforzada: boolean;
  motivo_rechazo: string | null;
  // Gestión documental en la postulación (Fase 2). El backend ya los exponía
  // en `SolicitudOut.documentos`; esta pantalla simplemente no los mostraba,
  // así que quien decidía aprobar o rechazar lo hacía sin ver un solo
  // documento. Vacío en solicitudes anteriores a esa ronda: es el estado real
  // de esos registros, no un error de carga.
  documentos: DocumentoSolicitud[];
}

interface DocumentoSolicitud {
  tipo: string;
  propietario_tipo: string;
  archivo_id: string;
  fecha_emision: string | null;
  fecha_vencimiento: string | null;
}

/** Vigencia de un documento de la postulación, calculada contra HOY. No es un
 * estado guardado: los documentos de una solicitud todavía no existen en la
 * colección `documentos` (se crean recién al aprobar), así que el control de
 * vigencia diario aún no los ha tocado. Sirve para que quien revisa vea de
 * entrada si le están mandando una licencia ya vencida. */
function vigenciaDocumento(fechaVencimiento: string | null): {
  texto: string;
  tono: "neutral" | "exito" | "advertencia" | "peligro";
} {
  if (!fechaVencimiento) return { texto: "Sin fecha", tono: "neutral" };
  const hoy = new Date();
  hoy.setHours(0, 0, 0, 0);
  const dias = Math.round((new Date(`${fechaVencimiento}T00:00:00`).getTime() - hoy.getTime()) / 86400000);
  if (dias < 0) return { texto: `Vencido hace ${Math.abs(dias)} d`, tono: "peligro" };
  if (dias <= 30) return { texto: `Vence en ${dias} d`, tono: "advertencia" };
  return { texto: "Vigente", tono: "exito" };
}

interface SolicitudListOut {
  items: Solicitud[];
  total: number;
}

// El estado de la solicitud ya no se pinta como píldora de color: va en el
// riel, que además muestra cuánto le falta al trayecto (ver `trayectos.ts`
// en shared-ui). El mapa de tonos por estado que vivía acá quedó sin uso.

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

      {/* Bitácora de revisión (segunda pasada, punto 1): "Nuevo" y "Eliminar"
          quitados por completo (no solo deshabilitados) -- las solicitudes
          las crea el propio postulante desde su registro público (nunca el
          personal interno) y no se eliminan, solo cambian de estado. Ningún
          rol que llega a este workpanel tiene un uso real para ninguno de
          los dos. */}
      <ActionBar
        actualizar={{ onClick: () => refetch() }}
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
                  <Riel {...trayectoSolicitud(s.estado)} variante="etiquetado" />
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
          ocultarContador
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
                  <Button
                    variant="secondary"
                    onClick={tomar}
                    loading={tomando}
                    title="Te asigna esta solicitud para revisarla — evita que otro compañero la revise al mismo tiempo."
                  >
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
              <DetailField label="Licencia" value={seleccionada.licencia_numero} />
              <DetailField
                label="Vehículo"
                value={`${seleccionada.vehiculo.placa} — ${seleccionada.vehiculo.marca} ${seleccionada.vehiculo.modelo} ${seleccionada.vehiculo.anio}, ${seleccionada.vehiculo.color}`}
              />
              <DetailField label="Estado" value={<Riel {...trayectoSolicitud(seleccionada.estado)} />} />
              <DetailField label="Revisión reforzada" value={seleccionada.revision_reforzada ? "Sí" : "No"} />
              <DetailField label="Fecha de envío" value={seleccionada.fecha_envio ? new Date(seleccionada.fecha_envio).toLocaleString() : "—"} />
              <DetailField label="Fecha de decisión" value={seleccionada.fecha_decision ? new Date(seleccionada.fecha_decision).toLocaleString() : "—"} />
              <DetailField label="Motivo de rechazo" value={seleccionada.motivo_rechazo ?? "—"} />
            </div>

            {/* Fase 2: revisión de los documentos enviados. Se ven de verdad
                (mismo visor de evidencia del resto del sistema, con
                ampliación a pantalla completa), con su fecha de caducidad y
                un semáforo de vigencia calculado contra hoy. La decisión en sí
                no estrena una máquina de estados propia: aprobar u observar la
                documentación ES la decisión de la solicitud
                (APROBADA/OBSERVADA/RECHAZADA, con motivo obligatorio cuando no
                es aprobación), que ya existía abajo en este mismo panel. */}
            <div style={{ borderTop: "1px solid var(--color-border)", paddingTop: "var(--space-3)" }}>
              <h3 style={{ margin: 0, marginBottom: "var(--space-2)", fontSize: "var(--font-size-md)" }}>
                Documentos enviados
              </h3>
              {seleccionada.documentos.length === 0 ? (
                <p style={{ margin: 0, color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
                  Esta solicitud no trae documentos adjuntos. Las solicitudes creadas antes de que el
                  formulario de postulación permitiera cargarlos quedan así — no es un fallo de carga.
                </p>
              ) : (
                <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-4)" }}>
                  {seleccionada.documentos.map((d) => {
                    const vigencia = vigenciaDocumento(d.fecha_vencimiento);
                    return (
                      <div
                        key={d.archivo_id}
                        style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)", minWidth: 200 }}
                      >
                        <strong style={{ fontSize: "var(--font-size-sm)" }}>{nombreTipoDocumento(d.tipo)}</strong>
                        <EvidenciaImagen archivoId={d.archivo_id} tamano={200} alt={`Documento ${nombreTipoDocumento(d.tipo)}`} />
                        <span style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>
                          Caduca: {d.fecha_vencimiento ? new Date(d.fecha_vencimiento).toLocaleDateString() : "—"}
                        </span>
                        <div>
                          <Badge texto={vigencia.texto} tono={vigencia.tono} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
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
