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
  Pagination,
  Select,
  TextField,
  type ModoPanel,
} from "@urbanflet/shared-ui";
import { useEffect, useState } from "react";

interface Viaje {
  id: string;
  pasajero_id: string;
  conductor_id: string | null;
  estado: string;
  origen_direccion: string;
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
  vehiculo_placa: string | null;
  pasajero_nombre: string | null;
  pasajero_calificacion: number | null;
  calificacion_pasajero_a_conductor: number | null;
  calificacion_conductor_a_pasajero: number | null;
}

interface HistorialOut {
  viajes: Viaje[];
  total: number;
}

const tonoPorEstado: Record<string, "neutral" | "exito" | "advertencia" | "peligro"> = {
  FINALIZADO: "exito",
  PAGADO: "exito",
  CANCELADO: "peligro",
  SIN_CONDUCTOR: "peligro",
};

/** Sección 3.3 de `specs/specs-administrativas/ux_complementaria.md` —
 * historial navegable de todos los viajes de la cooperativa (no solo
 * los propios). Patrón WorkPanel estándar, solo lectura (sin verbos de
 * edición: un viaje ya cerrado no se modifica desde acá). Sin filtro de
 * zona -- gap ya conocido, `viajes.zona_origen_id`/`zona_destino_id`
 * nunca se resuelven (mismo límite documentado en el Panel de Flota). */
export function SeccionHistorialGlobal() {
  const [viajes, setViajes] = useState<Viaje[]>([]);
  const [total, setTotal] = useState(0);
  const [filtroEstado, setFiltroEstado] = useState("");
  const [filtroTexto, setFiltroTexto] = useState("");
  const [textoInput, setTextoInput] = useState("");
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(20);

  const [seleccionado, setSeleccionado] = useState<Viaje | null>(null);
  const [modo, setModo] = useState<ModoPanel>("consulta");
  const [error, setError] = useState<unknown>(null);

  const cargar = async () => {
    const params = new URLSearchParams();
    if (filtroEstado) params.set("estado", filtroEstado);
    if (filtroTexto) params.set("texto", filtroTexto);
    if (desde) params.set("desde", new Date(desde).toISOString());
    if (hasta) params.set("hasta", new Date(hasta).toISOString());
    params.set("limite", String(pageSize));
    params.set("pagina", String(page + 1));
    const datos = await apiFetch<HistorialOut>(`/viajes/historial-global?${params.toString()}`);
    setViajes(datos.viajes);
    setTotal(datos.total);
  };

  useEffect(() => {
    cargar().catch(setError);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtroEstado, filtroTexto, desde, hasta, page, pageSize]);

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
    setError(null);
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

      <ActionBar
        nuevo={{ onClick: () => {}, disabled: true, title: "No aplica: los viajes los crean los pasajeros, no el personal interno." }}
        actualizar={{ onClick: () => cargar() }}
        eliminar={{ onClick: () => {}, disabled: true, title: "No aplica: un viaje histórico no se elimina." }}
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
            { header: "Pasajero", render: (v) => v.pasajero_nombre ?? "—" },
            { header: "Conductor", render: (v) => v.conductor_nombre ?? "—" },
            { header: "Estado", render: (v) => <Badge texto={v.estado} tono={tonoPorEstado[v.estado] ?? "neutral"} /> },
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
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "var(--space-3)" }}>
            <DetailField label="Pasajero" value={seleccionado.pasajero_nombre ?? "—"} />
            <DetailField label="Calificación del pasajero" value={seleccionado.pasajero_calificacion ?? "—"} />
            <DetailField label="Conductor" value={seleccionado.conductor_nombre ?? "—"} />
            <DetailField label="Calificación del conductor" value={seleccionado.conductor_calificacion ?? "—"} />
            <DetailField label="Vehículo" value={seleccionado.vehiculo_placa ?? "—"} />
            <DetailField label="Estado" value={<Badge texto={seleccionado.estado} tono={tonoPorEstado[seleccionado.estado] ?? "neutral"} />} />
            <DetailField label="Franja" value={seleccionado.franja} />
            <DetailField label="Origen" value={seleccionado.origen_direccion} />
            <DetailField label="Destino" value={seleccionado.destino_direccion ?? "—"} />
            <DetailField label="Solicitado" value={new Date(seleccionado.ts_solicitud).toLocaleString()} />
            <DetailField label="Finalizado" value={seleccionado.ts_fin ? new Date(seleccionado.ts_fin).toLocaleString() : "—"} />
            <DetailField label="Km recorridos" value={seleccionado.km_recorridos ?? "—"} />
            <DetailField label="Tarifa final" value={seleccionado.tarifa_final !== null ? `$${seleccionado.tarifa_final.toFixed(2)}` : "—"} />
            <DetailField label="Motivo de cancelación" value={seleccionado.motivo_cancelacion ?? "—"} />
            <DetailField label="Calificación pasajero → conductor" value={seleccionado.calificacion_pasajero_a_conductor ?? "—"} />
            <DetailField label="Calificación conductor → pasajero" value={seleccionado.calificacion_conductor_a_pasajero ?? "—"} />
          </div>
        </DetailPanel>
      )}
    </div>
  );
}
