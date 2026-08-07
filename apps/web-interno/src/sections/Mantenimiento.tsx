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

interface Repuesto {
  descripcion: string;
  cantidad: number;
  costo_unitario: number;
}

interface Orden {
  id: string;
  vehiculo_id: string;
  vehiculo_placa: string | null;
  tipo: string;
  estado: string;
  descripcion: string;
  km_entrada: number;
  km_salida: number | null;
  taller: string;
  fecha_programada: string;
  costo_total: number | null;
  repuestos_estimados: Repuesto[];
  repuestos_consumidos: Repuesto[];
  horas_taller: number | null;
}

interface OrdenListOut {
  items: Orden[];
  total: number;
}

interface VehiculoBusqueda {
  id: string;
  placa: string;
  marca: string;
  modelo: string;
  estado_habilitacion: string;
}

const tonoPorEstado: Record<string, "neutral" | "exito" | "advertencia" | "peligro"> = {
  ABIERTA: "neutral",
  EN_TALLER: "advertencia",
  CERRADA: "exito",
  ANULADA: "peligro",
};

type AccionOrden = "ninguna" | "cierre" | "anulacion";

const REPUESTO_VACIO: Repuesto = { descripcion: "", cantidad: 1, costo_unitario: 0 };

// Editor de línea de repuestos reutilizado en el formulario de creación
// (repuestos_estimados) y en el de cierre (repuestos_consumidos) — mismo
// shape (descripcion/cantidad/costo_unitario) en ambos, ver RepuestoInput
// en backend/src/mantenimiento/schemas.py.
function RepuestosEditor({
  repuestos,
  onChange,
}: {
  repuestos: Repuesto[];
  onChange: (repuestos: Repuesto[]) => void;
}) {
  const actualizar = (i: number, campo: keyof Repuesto, valor: string) => {
    const copia = repuestos.slice();
    copia[i] = {
      ...copia[i],
      [campo]: campo === "descripcion" ? valor : Number(valor),
    };
    onChange(copia);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
      <span style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>Repuestos</span>
      {repuestos.map((r, i) => (
        <div key={i} style={{ display: "flex", gap: "var(--space-2)", alignItems: "flex-end" }}>
          <div style={{ flex: 2 }}>
            <TextField label="Descripción" value={r.descripcion} onChange={(e) => actualizar(i, "descripcion", e.target.value)} />
          </div>
          <div style={{ flex: 1 }}>
            <TextField label="Cantidad" type="number" value={String(r.cantidad)} onChange={(e) => actualizar(i, "cantidad", e.target.value)} />
          </div>
          <div style={{ flex: 1 }}>
            <TextField
              label="Costo unitario"
              type="number"
              value={String(r.costo_unitario)}
              onChange={(e) => actualizar(i, "costo_unitario", e.target.value)}
            />
          </div>
          <div style={{ minWidth: 90 }}>
            <Button variant="secondary" onClick={() => onChange(repuestos.filter((_, j) => j !== i))}>
              Quitar
            </Button>
          </div>
        </div>
      ))}
      <div style={{ minWidth: 160 }}>
        <Button variant="secondary" onClick={() => onChange([...repuestos, { ...REPUESTO_VACIO }])}>
          Agregar repuesto
        </Button>
      </div>
    </div>
  );
}

// Misma convención de "Salir" que Solicitudes y Finanzas: en la barra fija
// de acciones limpia los criterios de búsqueda y vuelve a la lista por
// defecto; dentro del panel de detalle cierra sin aplicar cambios.
export function SeccionMantenimiento() {
  const [ordenes, setOrdenes] = useState<Orden[]>([]);
  const [total, setTotal] = useState(0);
  const [filtroPlaca, setFiltroPlaca] = useState("");
  const [placaInput, setPlacaInput] = useState("");
  const [filtroEstado, setFiltroEstado] = useState("");
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [error, setError] = useState<string | null>(null);

  const [seleccionada, setSeleccionada] = useState<Orden | null>(null);
  const [modo, setModo] = useState<ModoPanel>("consulta");
  const [accion, setAccion] = useState<AccionOrden>("ninguna");

  // --- Campos del formulario "Nuevo registro" (crear orden) ---
  const [placaBuscada, setPlacaBuscada] = useState("");
  const [resultadosVehiculo, setResultadosVehiculo] = useState<VehiculoBusqueda[]>([]);
  const [vehiculoId, setVehiculoId] = useState("");
  const [tipo, setTipo] = useState<"PREVENTIVA" | "CORRECTIVA">("PREVENTIVA");
  const [descripcion, setDescripcion] = useState("");
  const [kmEntrada, setKmEntrada] = useState("");
  const [taller, setTaller] = useState("");
  const [fechaProgramada, setFechaProgramada] = useState("");
  const [retirar, setRetirar] = useState(false);
  const [repuestosEstimados, setRepuestosEstimados] = useState<Repuesto[]>([]);

  // --- Campos del formulario de cierre ---
  const [costoCierre, setCostoCierre] = useState("");
  const [kmSalidaCierre, setKmSalidaCierre] = useState("");
  const [trabajosCierre, setTrabajosCierre] = useState("");
  const [repuestosConsumidos, setRepuestosConsumidos] = useState<Repuesto[]>([]);
  const [horasTallerCierre, setHorasTallerCierre] = useState("");
  const [ajusteJustificado, setAjusteJustificado] = useState(false);
  const [motivoAjuste, setMotivoAjuste] = useState("");

  // --- Campos del formulario de anulación ---
  const [motivoAnulacion, setMotivoAnulacion] = useState("");

  const [cargando, setCargando] = useState(false);

  const cargar = async () => {
    const params = new URLSearchParams();
    if (filtroPlaca) params.set("placa", filtroPlaca);
    if (filtroEstado) params.set("estado", filtroEstado);
    params.set("limit", String(pageSize));
    params.set("offset", String(page * pageSize));
    const datos = await apiFetch<OrdenListOut>(`/mantenimiento/ordenes?${params.toString()}`);
    setOrdenes(datos.items);
    setTotal(datos.total);
  };

  useEffect(() => {
    cargar().catch((e) => setError(e instanceof ApiError ? e.message : "No se pudieron cargar las órdenes"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtroPlaca, filtroEstado, page, pageSize]);

  const buscar = () => {
    setFiltroPlaca(placaInput.trim());
    setPage(0);
  };

  const limpiarBusqueda = () => {
    setFiltroPlaca("");
    setPlacaInput("");
    setFiltroEstado("");
    setPage(0);
    setSeleccionada(null);
  };

  const resetFormularioNuevo = () => {
    setPlacaBuscada("");
    setResultadosVehiculo([]);
    setVehiculoId("");
    setTipo("PREVENTIVA");
    setDescripcion("");
    setKmEntrada("");
    setTaller("");
    setFechaProgramada("");
    setRetirar(false);
    setRepuestosEstimados([]);
  };

  const abrirNuevo = () => {
    resetFormularioNuevo();
    setSeleccionada(null);
    setAccion("ninguna");
    setModo("nuevo");
    setError(null);
  };

  const abrirDetalle = (o: Orden) => {
    setSeleccionada(o);
    setAccion("ninguna");
    setModo("consulta");
    setCostoCierre("");
    setKmSalidaCierre(String(o.km_entrada));
    setTrabajosCierre("");
    setRepuestosConsumidos([]);
    setHorasTallerCierre("");
    setAjusteJustificado(false);
    setMotivoAjuste("");
    setMotivoAnulacion("");
    setError(null);
  };

  const buscarVehiculo = async () => {
    if (!placaBuscada) return;
    try {
      const datos = await apiFetch<VehiculoBusqueda[]>(
        `/mantenimiento/vehiculos/buscar?placa=${encodeURIComponent(placaBuscada)}`,
      );
      setResultadosVehiculo(datos);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo buscar el vehículo");
    }
  };

  const crearOrden = async () => {
    setError(null);
    setCargando(true);
    try {
      await apiFetch("/mantenimiento/ordenes", {
        method: "POST",
        body: {
          vehiculo_id: vehiculoId,
          tipo,
          descripcion,
          km_entrada: Number(kmEntrada),
          taller,
          fecha_programada: fechaProgramada,
          retirar_vehiculo: retirar,
          repuestos_estimados: repuestosEstimados,
        },
      });
      setModo("consulta");
      resetFormularioNuevo();
      await cargar();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo crear la orden");
    } finally {
      setCargando(false);
    }
  };

  const marcarEnTaller = async (id: string) => {
    setError(null);
    setCargando(true);
    try {
      await apiFetch(`/mantenimiento/ordenes/${id}/taller`, { method: "POST" });
      setSeleccionada(null);
      await cargar();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo marcar en taller");
    } finally {
      setCargando(false);
    }
  };

  const cerrarOrden = async () => {
    if (!seleccionada) return;
    setError(null);
    setCargando(true);
    try {
      await apiFetch(`/mantenimiento/ordenes/${seleccionada.id}/cierre`, {
        method: "POST",
        body: {
          trabajos_realizados: trabajosCierre,
          repuestos_consumidos: repuestosConsumidos,
          costo_total: Number(costoCierre),
          horas_taller: horasTallerCierre ? Number(horasTallerCierre) : null,
          km_salida: Number(kmSalidaCierre),
          habilitar_vehiculo: true,
          ajuste_justificado: ajusteJustificado,
          motivo_ajuste: ajusteJustificado ? motivoAjuste : null,
        },
      });
      setSeleccionada(null);
      setAccion("ninguna");
      await cargar();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo cerrar la orden");
    } finally {
      setCargando(false);
    }
  };

  const anularOrden = async () => {
    if (!seleccionada) return;
    setError(null);
    setCargando(true);
    try {
      await apiFetch(`/mantenimiento/ordenes/${seleccionada.id}/anulacion`, {
        method: "POST",
        body: { motivo: motivoAnulacion },
      });
      setSeleccionada(null);
      setAccion("ninguna");
      await cargar();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo anular la orden");
    } finally {
      setCargando(false);
    }
  };

  const iniciarCierre = () => {
    setAccion("cierre");
    setModo("edicion");
  };
  const iniciarAnulacion = () => {
    setAccion("anulacion");
    setModo("edicion");
  };

  const placaSeleccionada = seleccionada
    ? (seleccionada.vehiculo_placa ?? `vehículo ${seleccionada.vehiculo_id.slice(0, 8)}…`)
    : "";

  const tituloDetalle = seleccionada
    ? accion === "cierre"
      ? `Cerrar orden — ${placaSeleccionada}`
      : accion === "anulacion"
        ? `Anular orden — ${placaSeleccionada}`
        : `Orden de mantenimiento — ${placaSeleccionada}`
    : "Nueva orden de mantenimiento";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <Card>
        <h2 style={{ marginTop: 0, fontSize: "var(--font-size-lg)" }}>Buscar órdenes de mantenimiento</h2>
        <div style={{ display: "flex", gap: "var(--space-3)", flexWrap: "wrap", alignItems: "flex-end" }}>
          <div style={{ minWidth: 220 }}>
            <TextField
              label="Placa del vehículo"
              value={placaInput}
              onChange={(e) => setPlacaInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && buscar()}
            />
          </div>
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
                { value: "ABIERTA", label: "Abierta" },
                { value: "EN_TALLER", label: "En taller" },
                { value: "CERRADA", label: "Cerrada" },
                { value: "ANULADA", label: "Anulada" },
              ]}
            />
          </div>
        </div>
      </Card>

      <ActionBar
        nuevo={{ onClick: abrirNuevo }}
        actualizar={{ onClick: () => cargar() }}
        eliminar={{
          onClick: () => {},
          disabled: true,
          title: "No aplica: las órdenes no se eliminan, solo se cierran o se anulan.",
        }}
        buscar={{ onClick: buscar }}
        salir={{ onClick: limpiarBusqueda }}
      />

      <Card>
        {error && !seleccionada && modo !== "nuevo" && (
          <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>
        )}
        <DataTable
          rows={ordenes}
          keyField={(o) => o.id}
          vacio="No hay órdenes registradas."
          columns={[
            {
              header: "Vehículo",
              render: (o) =>
                o.vehiculo_placa ?? (
                  <span style={{ color: "var(--color-text-muted)", fontStyle: "italic" }} title={o.vehiculo_id}>
                    Sin placa ({o.vehiculo_id.slice(0, 8)}…)
                  </span>
                ),
            },
            { header: "Tipo", render: (o) => o.tipo },
            { header: "Estado", render: (o) => <Badge texto={o.estado} tono={tonoPorEstado[o.estado] ?? "neutral"} /> },
            { header: "Taller", render: (o) => o.taller },
            { header: "Costo", render: (o) => (o.costo_total != null ? `$${o.costo_total.toFixed(2)}` : "—") },
            {
              header: "Detalle",
              render: (o) => (
                <Button variant="secondary" onClick={() => abrirDetalle(o)}>
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

      {modo === "nuevo" && (
        <DetailPanel
          titulo={tituloDetalle}
          modo="nuevo"
          onSalir={() => setModo("consulta")}
          onAceptar={crearOrden}
          aceptarLabel="Crear orden"
          aceptarLoading={cargando}
          aceptarDisabled={!vehiculoId || !descripcion || !kmEntrada || !taller || !fechaProgramada}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            {error && <span style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</span>}
            <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "flex-end" }}>
              <TextField label="Buscar vehículo por placa" value={placaBuscada} onChange={(e) => setPlacaBuscada(e.target.value)} />
              <div style={{ minWidth: 120 }}>
                <Button variant="secondary" onClick={buscarVehiculo} disabled={!placaBuscada}>
                  Buscar
                </Button>
              </div>
            </div>
            {resultadosVehiculo.length > 0 && (
              <Select
                label="Vehículo"
                value={vehiculoId}
                onChange={(e) => setVehiculoId(e.target.value)}
                options={[
                  { value: "", label: "Selecciona un vehículo" },
                  ...resultadosVehiculo.map((v) => ({
                    value: v.id,
                    label: `${v.placa} — ${v.marca} ${v.modelo} (${v.estado_habilitacion})`,
                  })),
                ]}
              />
            )}
            <Select
              label="Tipo"
              value={tipo}
              onChange={(e) => setTipo(e.target.value as typeof tipo)}
              options={[
                { value: "PREVENTIVA", label: "Preventiva" },
                { value: "CORRECTIVA", label: "Correctiva" },
              ]}
            />
            <TextField label="Descripción" value={descripcion} onChange={(e) => setDescripcion(e.target.value)} />
            <TextField label="Kilometraje de entrada" type="number" value={kmEntrada} onChange={(e) => setKmEntrada(e.target.value)} />
            <TextField label="Taller" value={taller} onChange={(e) => setTaller(e.target.value)} />
            <TextField label="Fecha programada" type="date" value={fechaProgramada} onChange={(e) => setFechaProgramada(e.target.value)} />
            <label style={{ display: "flex", gap: "var(--space-2)", fontSize: "var(--font-size-sm)" }}>
              <input type="checkbox" checked={retirar} onChange={(e) => setRetirar(e.target.checked)} />
              Retirar el vehículo de servicio mientras dure la orden
            </label>
            <RepuestosEditor repuestos={repuestosEstimados} onChange={setRepuestosEstimados} />
          </div>
        </DetailPanel>
      )}

      {seleccionada && (
        <DetailPanel
          titulo={tituloDetalle}
          modo={modo}
          onSalir={() => {
            setSeleccionada(null);
            setAccion("ninguna");
          }}
          onAceptar={accion === "cierre" ? cerrarOrden : accion === "anulacion" ? anularOrden : undefined}
          aceptarLabel={accion === "cierre" ? "Cerrar y habilitar vehículo" : accion === "anulacion" ? "Confirmar anulación" : "Aceptar"}
          aceptarLoading={cargando}
          aceptarDisabled={
            accion === "cierre"
              ? !costoCierre ||
                !kmSalidaCierre ||
                !trabajosCierre ||
                (seleccionada !== null &&
                  Number(kmSalidaCierre) < seleccionada.km_entrada &&
                  (!ajusteJustificado || !motivoAjuste))
              : accion === "anulacion"
                ? !motivoAnulacion
                : false
          }
          accionesExtra={
            accion === "ninguna" ? (
              <>
                {seleccionada.estado === "ABIERTA" && (
                  <>
                    <div style={{ minWidth: 140 }}>
                      <Button variant="secondary" onClick={() => marcarEnTaller(seleccionada.id)} loading={cargando}>
                        En taller
                      </Button>
                    </div>
                    <div style={{ minWidth: 140 }}>
                      <Button variant="danger" onClick={iniciarAnulacion}>
                        Anular
                      </Button>
                    </div>
                  </>
                )}
                {seleccionada.estado === "EN_TALLER" && (
                  <div style={{ minWidth: 140 }}>
                    <Button onClick={iniciarCierre}>Cerrar</Button>
                  </div>
                )}
              </>
            ) : undefined
          }
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
            {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "var(--space-3)" }}>
              <DetailField label="Vehículo" value={seleccionada.vehiculo_placa ?? `Sin placa (${seleccionada.vehiculo_id})`} />
              <DetailField label="Tipo" value={seleccionada.tipo} />
              <DetailField label="Estado" value={<Badge texto={seleccionada.estado} tono={tonoPorEstado[seleccionada.estado] ?? "neutral"} />} />
              <DetailField label="Taller" value={seleccionada.taller} />
              <DetailField label="Descripción" value={seleccionada.descripcion} />
              <DetailField label="Km entrada" value={seleccionada.km_entrada} />
              <DetailField label="Km salida" value={seleccionada.km_salida ?? "—"} />
              <DetailField label="Fecha programada" value={new Date(seleccionada.fecha_programada).toLocaleDateString()} />
              <DetailField label="Costo total" value={seleccionada.costo_total != null ? `$${seleccionada.costo_total.toFixed(2)}` : "—"} />
              <DetailField label="Horas de taller" value={seleccionada.horas_taller ?? "—"} />
              <DetailField
                label="Repuestos estimados"
                value={
                  seleccionada.repuestos_estimados.length
                    ? seleccionada.repuestos_estimados.map((r) => `${r.cantidad}× ${r.descripcion}`).join(", ")
                    : "—"
                }
              />
              <DetailField
                label="Repuestos consumidos"
                value={
                  seleccionada.repuestos_consumidos.length
                    ? seleccionada.repuestos_consumidos.map((r) => `${r.cantidad}× ${r.descripcion}`).join(", ")
                    : "—"
                }
              />
            </div>

            {accion === "cierre" && (
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", borderTop: "1px solid var(--color-border)", paddingTop: "var(--space-3)" }}>
                <TextField label="Trabajos realizados" value={trabajosCierre} onChange={(e) => setTrabajosCierre(e.target.value)} />
                <TextField label="Costo total" type="number" value={costoCierre} onChange={(e) => setCostoCierre(e.target.value)} />
                <TextField label="Horas de taller" type="number" value={horasTallerCierre} onChange={(e) => setHorasTallerCierre(e.target.value)} />
                <TextField label="Kilometraje de salida" type="number" value={kmSalidaCierre} onChange={(e) => setKmSalidaCierre(e.target.value)} />
                <RepuestosEditor repuestos={repuestosConsumidos} onChange={setRepuestosConsumidos} />
                {/* CU-O13: km_salida &lt; km_entrada bloquea el cierre a menos que
                    se marque un ajuste justificado con motivo — antes el Jefe
                    de Mantenimiento no tenía forma de pasar por aquí en la UI
                    aunque el backend ya lo soportaba. */}
                {kmSalidaCierre !== "" && Number(kmSalidaCierre) < seleccionada.km_entrada && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
                    <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)", margin: 0 }}>
                      El kilometraje de salida es menor al de entrada — requiere un ajuste justificado.
                    </p>
                    <label style={{ display: "flex", gap: "var(--space-2)", fontSize: "var(--font-size-sm)" }}>
                      <input type="checkbox" checked={ajusteJustificado} onChange={(e) => setAjusteJustificado(e.target.checked)} />
                      Ajuste de kilometraje justificado
                    </label>
                    {ajusteJustificado && (
                      <TextField label="Motivo del ajuste" value={motivoAjuste} onChange={(e) => setMotivoAjuste(e.target.value)} />
                    )}
                  </div>
                )}
              </div>
            )}

            {accion === "anulacion" && (
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", borderTop: "1px solid var(--color-border)", paddingTop: "var(--space-3)" }}>
                <TextField label="Motivo" value={motivoAnulacion} onChange={(e) => setMotivoAnulacion(e.target.value)} />
              </div>
            )}
          </div>
        </DetailPanel>
      )}
    </div>
  );
}
