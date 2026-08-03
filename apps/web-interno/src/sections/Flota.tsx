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
} from "@urbanflet/shared-ui";
import { useEffect, useMemo, useState } from "react";

interface EstadoVehiculo {
  vehiculo_id: string;
  vehiculo_placa: string | null;
  conductor_id: string;
  conductor_nombre: string | null;
  estado_servicio: string;
  lat: number | null;
  lon: number | null;
  ts_servidor: string | null;
  sin_senal: boolean;
}

const tonoPorEstado: Record<string, "neutral" | "exito" | "advertencia" | "peligro"> = {
  DISPONIBLE: "exito",
  OCUPADO: "advertencia",
  "SIN_SEÑAL": "peligro",
};

// Mismo patrón WorkPanel del resto de web-interno (Solicitudes/Mantenimiento/
// Finanzas): búsqueda + lista paginada + botonera fija + detalle. A
// diferencia de esas pantallas, GET /flota/tablero no pagina ni filtra en el
// servidor (es un tablero en vivo, no un listado CRUD) — la búsqueda y la
// paginación de acá son sobre el snapshot ya cargado en el cliente, que de
// todas formas se refresca cada 10s.
export function SeccionFlota() {
  const [vehiculos, setVehiculos] = useState<EstadoVehiculo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [actualizando, setActualizando] = useState(false);

  const [textoInput, setTextoInput] = useState("");
  const [filtroTexto, setFiltroTexto] = useState("");
  const [filtroEstado, setFiltroEstado] = useState("");
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(20);

  const [seleccionado, setSeleccionado] = useState<EstadoVehiculo | null>(null);

  const cargar = async () => {
    setActualizando(true);
    try {
      const datos = await apiFetch<EstadoVehiculo[]>("/flota/tablero");
      setVehiculos(datos);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo cargar el tablero de flota");
    } finally {
      setActualizando(false);
    }
  };

  useEffect(() => {
    cargar();
    const id = setInterval(cargar, 10000);
    return () => clearInterval(id);
  }, []);

  const filtrados = useMemo(() => {
    const texto = filtroTexto.trim().toLowerCase();
    return vehiculos.filter((v) => {
      if (filtroEstado && v.estado_servicio !== filtroEstado) return false;
      if (!texto) return true;
      return (
        (v.vehiculo_placa ?? "").toLowerCase().includes(texto) ||
        (v.conductor_nombre ?? "").toLowerCase().includes(texto)
      );
    });
  }, [vehiculos, filtroTexto, filtroEstado]);

  const paginados = filtrados.slice(page * pageSize, (page + 1) * pageSize);

  const buscar = () => {
    setFiltroTexto(textoInput.trim());
    setPage(0);
  };

  const limpiarBusqueda = () => {
    setTextoInput("");
    setFiltroTexto("");
    setFiltroEstado("");
    setPage(0);
    setSeleccionado(null);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <Card>
        <h2 style={{ marginTop: 0, fontSize: "var(--font-size-lg)" }}>Buscar en el tablero de flota</h2>
        <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)", marginTop: 0 }}>
          Se refresca automáticamente cada 10s. Solo se listan vehículos con turno activo.
        </p>
        <div style={{ display: "flex", gap: "var(--space-3)", flexWrap: "wrap", alignItems: "flex-end" }}>
          <div style={{ minWidth: 220 }}>
            <TextField
              label="Placa o conductor"
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
                { value: "DISPONIBLE", label: "Disponible" },
                { value: "OCUPADO", label: "Ocupado" },
                { value: "SIN_SEÑAL", label: "Sin señal" },
              ]}
            />
          </div>
        </div>
      </Card>

      <ActionBar
        nuevo={{
          onClick: () => {},
          disabled: true,
          title: "No aplica: un vehículo entra a la flota al aprobarse la postulación de su conductor (CU-O01), no desde acá.",
        }}
        actualizar={{ onClick: () => cargar(), loading: actualizando }}
        eliminar={{
          onClick: () => {},
          disabled: true,
          title: "No aplica: este tablero es de solo lectura, refleja el estado en vivo de la flota.",
        }}
        buscar={{ onClick: buscar }}
        salir={{ onClick: limpiarBusqueda }}
      />

      <Card>
        {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
        <DataTable
          rows={paginados}
          keyField={(v) => v.vehiculo_id}
          vacio="No hay vehículos en servicio con este filtro."
          columns={[
            {
              header: "Vehículo",
              render: (v) =>
                v.vehiculo_placa ?? (
                  <span style={{ color: "var(--color-text-muted)", fontStyle: "italic" }} title={v.vehiculo_id}>
                    Sin placa ({v.vehiculo_id.slice(0, 8)}…)
                  </span>
                ),
            },
            {
              header: "Conductor",
              render: (v) =>
                v.conductor_nombre ?? (
                  <span style={{ color: "var(--color-text-muted)", fontStyle: "italic" }} title={v.conductor_id}>
                    Sin nombre ({v.conductor_id.slice(0, 8)}…)
                  </span>
                ),
            },
            {
              header: "Estado",
              render: (v) => <Badge texto={v.estado_servicio} tono={tonoPorEstado[v.estado_servicio] ?? "neutral"} />,
            },
            { header: "Posición", render: (v) => (v.lat != null && v.lon != null ? `${v.lat.toFixed(4)}, ${v.lon.toFixed(4)}` : "—") },
            {
              header: "Última actualización",
              render: (v) => (v.ts_servidor ? new Date(v.ts_servidor).toLocaleTimeString() : "—"),
            },
            {
              header: "Detalle",
              render: (v) => (
                <Button variant="secondary" onClick={() => setSeleccionado(v)}>
                  Ver
                </Button>
              ),
            },
          ]}
        />
        <Pagination
          page={page}
          pageSize={pageSize}
          total={filtrados.length}
          onPageChange={setPage}
          onPageSizeChange={(n) => {
            setPageSize(n);
            setPage(0);
          }}
        />
      </Card>

      {seleccionado && (
        <DetailPanel
          titulo={`Vehículo — ${seleccionado.vehiculo_placa ?? seleccionado.vehiculo_id.slice(0, 8) + "…"}`}
          modo="consulta"
          onSalir={() => setSeleccionado(null)}
        >
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "var(--space-3)" }}>
            <DetailField label="Vehículo" value={seleccionado.vehiculo_placa ?? `Sin placa (${seleccionado.vehiculo_id})`} />
            <DetailField
              label="Conductor"
              value={seleccionado.conductor_nombre ?? `Sin nombre (${seleccionado.conductor_id})`}
            />
            <DetailField
              label="Estado"
              value={<Badge texto={seleccionado.estado_servicio} tono={tonoPorEstado[seleccionado.estado_servicio] ?? "neutral"} />}
            />
            <DetailField
              label="Posición"
              value={seleccionado.lat != null && seleccionado.lon != null ? `${seleccionado.lat.toFixed(5)}, ${seleccionado.lon.toFixed(5)}` : "—"}
            />
            <DetailField
              label="Última actualización"
              value={seleccionado.ts_servidor ? new Date(seleccionado.ts_servidor).toLocaleString() : "—"}
            />
            <DetailField label="Sin señal" value={seleccionado.sin_senal ? "Sí" : "No"} />
          </div>
        </DetailPanel>
      )}
    </div>
  );
}
