import {
  ActionBar,
  ApiError,
  apiFetch,
  Avatar,
  Button,
  Card,
  DataTable,
  DetailField,
  DetailPanel,
  MapaRutaViaje,
  Pagination,
  Riel,
  Select,
  TextField,
  trayectoViaje,
  useSwr,
  type ModoPanel,
} from "@urbanflet/shared-ui";
import { useState } from "react";

const RECURSO_HISTORIAL_GLOBAL = "/viajes/historial-global";

interface Viaje {
  id: string;
  pasajero_id: string;
  conductor_id: string | null;
  estado: string;
  // Coordenadas: el backend ya las devolvía siempre en `ViajeOut`, esta
  // interfaz simplemente no las tipaba porque no había mapa en esta pantalla.
  origen_lat: number;
  origen_lon: number;
  origen_direccion: string;
  destino_lat: number | null;
  destino_lon: number | null;
  destino_direccion: string | null;
  franja: string;
  ts_solicitud: string;
  ts_fin: string | null;
  km_recorridos: number | null;
  tarifa_final: number | null;
  tarifa_estimada: number | null;
  motivo_cancelacion: string | null;
  conductor_nombre: string | null;
  conductor_calificacion: number | null;
  conductor_foto_url: string | null;
  vehiculo_placa: string | null;
  pasajero_nombre: string | null;
  pasajero_calificacion: number | null;
  pasajero_foto_url: string | null;
  calificacion_pasajero_a_conductor: { puntaje: number; comentario: string | null; ts: string } | null;
  calificacion_conductor_a_pasajero: { puntaje: number; comentario: string | null; ts: string } | null;
}

interface HistorialOut {
  viajes: Viaje[];
  total: number;
}

// Fase 4 del Sistema Riel: esta pantalla mostraba el estado del viaje como
// píldora de color (`Badge`) con un `tonoPorEstado` propio -- el mismo
// enum crudo que las otras 3 pantallas de trayecto ya habían dejado atrás
// en la Fase 2. `trayectoViaje` ya existía en `trayectos.ts` desde esa
// fase, pero nunca se había cableado acá. Va en el riel, que además
// muestra cuánto le falta al trayecto.

/** Sección 3.3 de `specs/specs-administrativas/ux_complementaria.md` —
 * historial navegable de todos los viajes de la cooperativa (no solo
 * los propios). Patrón WorkPanel estándar, solo lectura (sin verbos de
 * edición: un viaje ya cerrado no se modifica desde acá). Sin filtro de
 * zona -- gap ya conocido, `viajes.zona_origen_id`/`zona_destino_id`
 * nunca se resuelven (mismo límite documentado en el Panel de Flota). */
export function SeccionHistorialGlobal() {
  const [filtroEstado, setFiltroEstado] = useState("");
  const [filtroTexto, setFiltroTexto] = useState("");
  const [textoInput, setTextoInput] = useState("");
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(20);

  const [seleccionado, setSeleccionado] = useState<Viaje | null>(null);
  const [modo, setModo] = useState<ModoPanel>("consulta");
  // Traza GPS del viaje abierto. Se pide aparte y solo al abrir el detalle:
  // la LISTA nunca la trae (ver `to_out(..., incluir_traza)` en el backend --
  // 20 filas con hasta 20 000 puntos cada una no tendría sentido). `undefined`
  // = todavía cargando, `null` = el viaje no tiene traza registrada.
  const [traza, setTraza] = useState<[number, number][] | null | undefined>(undefined);

  // Caché stale-while-revalidate (ver `swrCache.ts`): con un dataset de
  // ~1.3M viajes históricos (ver CLAUDE.md §7), volver a una combinación de
  // filtros/página ya visitada muestra la lista de inmediato desde caché en
  // vez de repetir la consulta completa contra Mongo, mientras se revalida
  // en segundo plano.
  const claveConsulta = (() => {
    const params = new URLSearchParams();
    if (filtroEstado) params.set("estado", filtroEstado);
    if (filtroTexto) params.set("texto", filtroTexto);
    if (desde) params.set("desde", new Date(desde).toISOString());
    if (hasta) params.set("hasta", new Date(hasta).toISOString());
    params.set("limite", String(pageSize));
    params.set("pagina", String(page + 1));
    return `${RECURSO_HISTORIAL_GLOBAL}?${params.toString()}`;
  })();
  const { data, error, refetch } = useSwr<HistorialOut>(claveConsulta, () => apiFetch<HistorialOut>(claveConsulta));
  const viajes = data?.viajes ?? [];
  const total = data?.total ?? 0;

  const buscar = () => {
    setFiltroTexto(textoInput.trim());
    setPage(0);
  };

  const limpiarBusqueda = () => {
    setFiltroEstado("");
    setTextoInput("");
    setFiltroTexto("");
    setDesde("");
    setHasta("");
    setPage(0);
    setSeleccionado(null);
  };

  const abrirDetalle = (v: Viaje) => {
    setSeleccionado(v);
    setModo("consulta");
    setTraza(undefined);
    // Ruta propia para roles internos: `GET /viajes/{id}` exige que el actor
    // sea el pasajero o el conductor del viaje, así que un supervisor siempre
    // recibiría el 404 genérico ahí. Un fallo acá no rompe el detalle -- el
    // mapa cae al estado "sin traza", que es la verdad más conservadora.
    apiFetch<{ traza: [number, number][] | null }>(`${RECURSO_HISTORIAL_GLOBAL}/${v.id}`)
      .then((r) => setTraza(r.traza ?? null))
      .catch(() => setTraza(null));
  };

  const mensajeGeneral =
    error instanceof ApiError ? error.message : error ? "No se pudo cargar el historial" : null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <Card>
        <h2 style={{ marginTop: 0, fontSize: "var(--font-size-lg)" }}>Historial de viajes</h2>
        <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
          Búsqueda de cualquier viaje histórico de la cooperativa por nombre de pasajero/conductor, estado o rango de
          fechas. Solo lectura — un viaje ya cerrado no se modifica desde aquí. El pasajero se muestra con nombre de
          pila y calificación únicamente, nunca su contacto completo.
        </p>
        <div style={{ display: "flex", gap: "var(--space-3)", flexWrap: "wrap", alignItems: "flex-end" }}>
          <div style={{ minWidth: 220 }}>
            <TextField
              label="Nombre de pasajero o conductor"
              value={textoInput}
              onChange={(e) => setTextoInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && buscar()}
            />
          </div>
          <div style={{ minWidth: 200 }}>
            <Select
              label="Estado"
              value={filtroEstado}
              onChange={(e) => {
                setFiltroEstado(e.target.value);
                setPage(0);
              }}
              options={[
                { value: "", label: "Todos" },
                { value: "FINALIZADO", label: "Finalizado" },
                { value: "PAGADO", label: "Pagado" },
                { value: "CANCELADO", label: "Cancelado" },
                { value: "SIN_CONDUCTOR", label: "Sin conductor" },
              ]}
            />
          </div>
          <div style={{ minWidth: 180 }}>
            <TextField
              label="Desde"
              type="date"
              value={desde}
              onChange={(e) => {
                setDesde(e.target.value);
                setPage(0);
              }}
            />
          </div>
          <div style={{ minWidth: 180 }}>
            <TextField
              label="Hasta"
              type="date"
              value={hasta}
              onChange={(e) => {
                setHasta(e.target.value);
                setPage(0);
              }}
            />
          </div>
        </div>
      </Card>

      {/* "Nuevo"/"Eliminar" quitados (segunda pasada, punto 1): los viajes
          los crean los pasajeros (nunca el personal interno) y un viaje
          histórico no se elimina -- ningún rol tiene un uso real para
          ninguno de los dos acá. */}
      <ActionBar
        actualizar={{ onClick: () => refetch() }}
        buscar={{ onClick: buscar }}
        salir={{ onClick: limpiarBusqueda }}
      />

      <Card>
        {mensajeGeneral && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{mensajeGeneral}</p>}
        <DataTable
          rows={viajes}
          keyField={(v) => v.id}
          vacio="No hay viajes con este filtro."
          columns={[
            {
              header: "Pasajero",
              render: (v) =>
                v.pasajero_nombre ? (
                  <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                    <Avatar fotoUrl={v.pasajero_foto_url} nombre={v.pasajero_nombre} tamano={28} />
                    {v.pasajero_nombre}
                  </div>
                ) : (
                  "—"
                ),
            },
            {
              header: "Conductor",
              render: (v) =>
                v.conductor_nombre ? (
                  <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                    <Avatar fotoUrl={v.conductor_foto_url} nombre={v.conductor_nombre} tamano={28} />
                    {v.conductor_nombre}
                  </div>
                ) : (
                  "—"
                ),
            },
            { header: "Estado", render: (v) => <Riel {...trayectoViaje(v.estado)} variante="etiquetado" /> },
            { header: "Solicitado", render: (v) => new Date(v.ts_solicitud).toLocaleString() },
            {
              header: "Detalle",
              render: (v) => (
                <Button variant="secondary" onClick={() => abrirDetalle(v)}>
                  Ver
                </Button>
              ),
            },
          ]}
          ocultarContador
        />
        <Pagination
          page={page}
          pageSize={pageSize}
          total={total}
          onPageChange={setPage}
          onPageSizeChange={(n) => {
            setPageSize(n);
            setPage(0);
          }}
        />
      </Card>

      {seleccionado && (
        <DetailPanel titulo={`Viaje — ${seleccionado.id}`} modo={modo} onSalir={() => setSeleccionado(null)}>
          {/* CU-O14 paso 3 llevado al historial global: mismo componente que
              usan web-pasajero y web-conductor. Solo dibuja la traza GPS real;
              si el viaje no la tiene (p. ej. los viajes históricos sembrados,
              que nacen sin traza) muestra origen/destino y lo declara. */}
          <div style={{ marginBottom: "var(--space-3)" }}>
            <MapaRutaViaje
              viajeId={seleccionado.id}
              origen={{ lat: seleccionado.origen_lat, lon: seleccionado.origen_lon }}
              destino={
                seleccionado.destino_lat !== null && seleccionado.destino_lon !== null
                  ? { lat: seleccionado.destino_lat, lon: seleccionado.destino_lon }
                  : null
              }
              traza={traza ?? null}
              origenDireccion={seleccionado.origen_direccion}
              destinoDireccion={seleccionado.destino_direccion}
            />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "var(--space-3)" }}>
            <DetailField
              label="Pasajero"
              value={
                seleccionado.pasajero_nombre ? (
                  <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                    <Avatar fotoUrl={seleccionado.pasajero_foto_url} nombre={seleccionado.pasajero_nombre} tamano={32} />
                    {seleccionado.pasajero_nombre}
                  </div>
                ) : (
                  "—"
                )
              }
            />
            <DetailField label="Calificación del pasajero" value={seleccionado.pasajero_calificacion ?? "—"} />
            <DetailField
              label="Conductor"
              value={
                seleccionado.conductor_nombre ? (
                  <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                    <Avatar fotoUrl={seleccionado.conductor_foto_url} nombre={seleccionado.conductor_nombre} tamano={32} />
                    {seleccionado.conductor_nombre}
                  </div>
                ) : (
                  "—"
                )
              }
            />
            <DetailField label="Calificación del conductor" value={seleccionado.conductor_calificacion ?? "—"} />
            <DetailField label="Vehículo" value={seleccionado.vehiculo_placa ?? "—"} />
            <DetailField label="Estado" value={<Riel {...trayectoViaje(seleccionado.estado)} />} />
            <DetailField label="Franja" value={seleccionado.franja} />
            <DetailField label="Origen" value={seleccionado.origen_direccion} />
            <DetailField label="Destino" value={seleccionado.destino_direccion ?? "—"} />
            <DetailField label="Solicitado" value={new Date(seleccionado.ts_solicitud).toLocaleString()} />
            <DetailField label="Finalizado" value={seleccionado.ts_fin ? new Date(seleccionado.ts_fin).toLocaleString() : "—"} />
            <DetailField label="Km recorridos" value={seleccionado.km_recorridos ?? "—"} />
            <DetailField label="Tarifa final" value={seleccionado.tarifa_final !== null ? `$${seleccionado.tarifa_final.toFixed(2)}` : "—"} />
            <DetailField label="Motivo de cancelación" value={seleccionado.motivo_cancelacion ?? "—"} />
            <DetailField
              label="Calificación pasajero → conductor"
              value={
                seleccionado.calificacion_pasajero_a_conductor
                  ? `${seleccionado.calificacion_pasajero_a_conductor.puntaje}★`
                  : "—"
              }
            />
            <DetailField
              label="Calificación conductor → pasajero"
              value={
                seleccionado.calificacion_conductor_a_pasajero
                  ? `${seleccionado.calificacion_conductor_a_pasajero.puntaje}★`
                  : "—"
              }
            />
          </div>
        </DetailPanel>
      )}
    </div>
  );
}
