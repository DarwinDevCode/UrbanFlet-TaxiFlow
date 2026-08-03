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
  TextArea,
  TextField,
  type ModoPanel,
} from "@urbanflet/shared-ui";
import { useEffect, useState, type ReactNode } from "react";

interface Pago {
  id: string;
  viaje_id: string;
  conductor_id: string;
  conductor_nombre: string | null;
  monto: number;
  tarifa_final: number;
  diferencia: number | null;
  estado: string;
  ts_registro: string;
}

interface ViajeSinPago {
  viaje_id: string;
  conductor_id: string;
  conductor_nombre: string | null;
  tarifa_final: number;
  ts_fin: string;
}

interface Bandeja {
  discrepancias: Pago[];
  viajes_sin_pago: ViajeSinPago[];
}

interface LiquidacionDetalleViaje {
  viaje_id: string;
  metodo: string;
  monto: number;
  comision: number;
  neto_socio: number;
  ts: string;
}

interface Liquidacion {
  id: string;
  conductor_id: string;
  conductor_nombre: string | null;
  periodo_inicio: string;
  periodo_fin: string;
  estado: string;
  bruto: number;
  comisiones: number;
  ajustes: number;
  neto: number;
  saldo: number;
  detalle: LiquidacionDetalleViaje[];
  observacion_motivo?: string | null;
  viajes_en_revision: number;
}

interface LiquidacionListOut {
  items: Liquidacion[];
  total: number;
}

interface GenerarLiquidacionesResponse {
  periodo_inicio: string;
  periodo_fin: string;
  generadas: Liquidacion[];
  ya_existian: string[];
}

interface AlertaSaldoNegativo {
  conductor_id: string;
  conductor_nombre: string | null;
  periodos_consecutivos: number;
  liquidaciones: Liquidacion[];
}

function nombreConductor(id: string, nombre: string | null): ReactNode {
  if (nombre) return nombre;
  return (
    <span style={{ color: "var(--color-text-muted)", fontStyle: "italic" }} title={id}>
      Conductor sin datos ({id.slice(0, 8)}…)
    </span>
  );
}

export function SeccionFinanzas() {
  const [bandeja, setBandeja] = useState<Bandeja>({ discrepancias: [], viajes_sin_pago: [] });
  const [liquidaciones, setLiquidaciones] = useState<Liquidacion[]>([]);
  const [totalLiquidaciones, setTotalLiquidaciones] = useState(0);
  const [filtroEstadoLiq, setFiltroEstadoLiq] = useState("");
  const [pageLiq, setPageLiq] = useState(0);
  const [pageSizeLiq, setPageSizeLiq] = useState(20);
  const [alertas, setAlertas] = useState<AlertaSaldoNegativo[]>([]);
  const [ultimoResultado, setUltimoResultado] = useState<GenerarLiquidacionesResponse | null>(null);
  const [generando, setGenerando] = useState(false);
  const [accionando, setAccionando] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pagoEnResolucion, setPagoEnResolucion] = useState<string | null>(null);
  const [motivo, setMotivo] = useState("");
  const [observacionEnRespuesta, setObservacionEnRespuesta] = useState<string | null>(null);
  const [respuestaMotivo, setRespuestaMotivo] = useState("");
  const [ajusteMonto, setAjusteMonto] = useState("");
  const [liquidacionSeleccionada, setLiquidacionSeleccionada] = useState<Liquidacion | null>(null);
  const [modoLiq, setModoLiq] = useState<ModoPanel>("consulta");

  const cargar = async () => {
    const datos = await apiFetch<Bandeja>("/pagos/discrepancias");
    setBandeja(datos);
  };

  const cargarLiquidaciones = async () => {
    const params = new URLSearchParams();
    if (filtroEstadoLiq) params.set("estado", filtroEstadoLiq);
    params.set("limit", String(pageSizeLiq));
    params.set("offset", String(pageLiq * pageSizeLiq));
    const datos = await apiFetch<LiquidacionListOut>(`/liquidaciones?${params.toString()}`);
    setLiquidaciones(datos.items);
    setTotalLiquidaciones(datos.total);
  };

  const cargarAlertas = async () => {
    const datos = await apiFetch<AlertaSaldoNegativo[]>("/liquidaciones/alertas-saldo-negativo");
    setAlertas(datos);
  };

  useEffect(() => {
    cargar().catch((e) => setError(e instanceof ApiError ? e.message : "No se pudo cargar la bandeja de discrepancias"));
    cargarAlertas().catch((e) =>
      setError(e instanceof ApiError ? e.message : "No se pudieron cargar las alertas de saldo negativo"),
    );
  }, []);

  useEffect(() => {
    cargarLiquidaciones().catch((e) =>
      setError(e instanceof ApiError ? e.message : "No se pudieron cargar las liquidaciones"),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtroEstadoLiq, pageLiq, pageSizeLiq]);

  const generarLiquidaciones = async () => {
    setError(null);
    setGenerando(true);
    try {
      const resultado = await apiFetch<GenerarLiquidacionesResponse>("/liquidaciones/generar", { method: "POST" });
      setUltimoResultado(resultado);
      await cargarLiquidaciones();
      await cargarAlertas();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo generar la liquidación del periodo");
    } finally {
      setGenerando(false);
    }
  };

  const aprobarLiquidacion = async (liquidacionId: string) => {
    setError(null);
    setAccionando(liquidacionId);
    try {
      await apiFetch(`/liquidaciones/${liquidacionId}/aprobar`, { method: "POST" });
      setLiquidacionSeleccionada(null);
      await cargarLiquidaciones();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo aprobar la liquidación");
    } finally {
      setAccionando(null);
    }
  };

  const pagarLiquidacion = async (liquidacionId: string) => {
    setError(null);
    setAccionando(liquidacionId);
    try {
      await apiFetch(`/liquidaciones/${liquidacionId}/pagar`, { method: "POST" });
      setLiquidacionSeleccionada(null);
      await cargarLiquidaciones();
      await cargarAlertas();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo confirmar el pago de la liquidación");
    } finally {
      setAccionando(null);
    }
  };

  const responderObservacion = async (liquidacionId: string, ratificar: boolean) => {
    setError(null);
    setAccionando(liquidacionId);
    try {
      const ajuste = ajusteMonto.trim() ? Number(ajusteMonto) : null;
      await apiFetch(`/liquidaciones/${liquidacionId}/responder-observacion`, {
        method: "POST",
        body: { ratificar, motivo: respuestaMotivo, ajuste_monto: ajuste },
      });
      setObservacionEnRespuesta(null);
      setRespuestaMotivo("");
      setAjusteMonto("");
      setLiquidacionSeleccionada(null);
      await cargarLiquidaciones();
      await cargarAlertas();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo responder a la observación");
    } finally {
      setAccionando(null);
    }
  };

  const abrirDetalleLiquidacion = (l: Liquidacion) => {
    setLiquidacionSeleccionada(l);
    setModoLiq(l.estado === "OBSERVADA" ? "edicion" : "consulta");
    setObservacionEnRespuesta(null);
    setRespuestaMotivo("");
    setAjusteMonto("");
    setError(null);
  };

  const limpiarBusquedaLiquidaciones = () => {
    setFiltroEstadoLiq("");
    setPageLiq(0);
    setLiquidacionSeleccionada(null);
  };

  const resolver = async (pagoId: string, aceptar: boolean) => {
    setError(null);
    try {
      await apiFetch(`/pagos/${pagoId}/resolver`, { method: "POST", body: { aceptar, motivo } });
      setPagoEnResolucion(null);
      setMotivo("");
      await cargar();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo resolver la discrepancia");
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}

      <Card>
        <h2 style={{ marginTop: 0, fontSize: "var(--font-size-lg)" }}>Pagos en discrepancia</h2>
        <p style={{ color: "var(--color-text-muted)" }}>
          Monto cobrado por el conductor distinto a la tarifa final calculada del viaje. Ningún pago aquí entra a
          liquidación hasta resolverse.
        </p>
        <DataTable
          rows={bandeja.discrepancias}
          keyField={(p) => p.id}
          vacio="No hay discrepancias pendientes."
          columns={[
            { header: "Viaje", render: (p) => p.viaje_id },
            { header: "Conductor", render: (p) => nombreConductor(p.conductor_id, p.conductor_nombre) },
            { header: "Tarifa final", render: (p) => `$${p.tarifa_final.toFixed(2)}` },
            { header: "Monto cobrado", render: (p) => `$${p.monto.toFixed(2)}` },
            {
              header: "Diferencia",
              render: (p) => (
                <Badge
                  texto={p.diferencia !== null ? `$${p.diferencia.toFixed(2)}` : "—"}
                  tono={p.diferencia !== null && p.diferencia < 0 ? "peligro" : "advertencia"}
                />
              ),
            },
            {
              header: "Acciones",
              render: (p) =>
                pagoEnResolucion === p.id ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)", minWidth: 240 }}>
                    <TextArea
                      label="Motivo de la resolución"
                      value={motivo}
                      onChange={(e) => setMotivo(e.target.value)}
                    />
                    <div style={{ display: "flex", gap: "var(--space-2)" }}>
                      <Button onClick={() => resolver(p.id, true)} disabled={!motivo.trim()}>
                        Aceptar monto cobrado
                      </Button>
                      <Button variant="danger" onClick={() => resolver(p.id, false)} disabled={!motivo.trim()}>
                        Rechazar
                      </Button>
                      <Button
                        variant="secondary"
                        onClick={() => {
                          setPagoEnResolucion(null);
                          setMotivo("");
                        }}
                      >
                        Cancelar
                      </Button>
                    </div>
                  </div>
                ) : (
                  <Button onClick={() => setPagoEnResolucion(p.id)}>Resolver</Button>
                ),
            },
          ]}
        />
      </Card>

      <Card>
        <h2 style={{ marginTop: 0, fontSize: "var(--font-size-lg)" }}>Viajes finalizados sin pago (+24h)</h2>
        <p style={{ color: "var(--color-text-muted)" }}>
          El conductor terminó el viaje pero nunca registró el cobro. Solo informativo por ahora — no hay una acción
          de resolución para este caso todavía.
        </p>
        <DataTable
          rows={bandeja.viajes_sin_pago}
          keyField={(v) => v.viaje_id}
          vacio="No hay viajes sin pago pendientes."
          columns={[
            { header: "Viaje", render: (v) => v.viaje_id },
            { header: "Conductor", render: (v) => nombreConductor(v.conductor_id, v.conductor_nombre) },
            { header: "Tarifa final", render: (v) => `$${v.tarifa_final.toFixed(2)}` },
            { header: "Finalizado", render: (v) => new Date(v.ts_fin).toLocaleString() },
          ]}
        />
      </Card>

      {alertas.length > 0 && (
        <Card>
          <h2 style={{ marginTop: 0, fontSize: "var(--font-size-lg)" }}>Alertas de saldo negativo</h2>
          <p style={{ color: "var(--color-text-muted)" }}>
            Socios con {alertas[0]?.periodos_consecutivos ?? 2} o más periodos consecutivos con saldo negativo sin
            confirmar el pago (deben la comisión de efectivo retenida). La suspensión de turno para estos casos
            todavía no está automatizada — requiere seguimiento manual.
          </p>
          <DataTable
            rows={alertas}
            keyField={(a) => a.conductor_id}
            vacio="Sin alertas."
            columns={[
              { header: "Conductor", render: (a) => nombreConductor(a.conductor_id, a.conductor_nombre) },
              { header: "Periodos negativos consecutivos", render: (a) => a.periodos_consecutivos },
              {
                header: "Saldo acumulado",
                render: (a) => (
                  <Badge
                    texto={`$${a.liquidaciones.reduce((acc, l) => acc + l.saldo, 0).toFixed(2)}`}
                    tono="peligro"
                  />
                ),
              },
            ]}
          />
        </Card>
      )}

      <Card>
        <h2 style={{ marginTop: 0, fontSize: "var(--font-size-lg)" }}>Buscar liquidaciones del periodo</h2>
        <p style={{ color: "var(--color-text-muted)" }}>
          Genera el lote de liquidaciones para el periodo semanal (viernes a viernes) más reciente ya cerrado. Un
          socio sin viajes pagados en el periodo simplemente no genera liquidación; volver a pulsar el botón no
          duplica las ya emitidas.
        </p>
        <div style={{ maxWidth: 320 }}>
          <Button onClick={generarLiquidaciones} loading={generando}>
            Generar liquidaciones del periodo cerrado
          </Button>
        </div>
        {ultimoResultado && (
          <p style={{ marginTop: "var(--space-3)", color: "var(--color-text-muted)" }}>
            Periodo {new Date(ultimoResultado.periodo_inicio).toLocaleDateString()} –{" "}
            {new Date(ultimoResultado.periodo_fin).toLocaleDateString()}: {ultimoResultado.generadas.length}{" "}
            liquidación(es) emitida(s), {ultimoResultado.ya_existian.length} ya existían.
          </p>
        )}

        <div style={{ marginTop: "var(--space-4)", maxWidth: 320 }}>
          <Select
            label="Estado"
            value={filtroEstadoLiq}
            onChange={(e) => {
              setFiltroEstadoLiq(e.target.value);
              setPageLiq(0);
            }}
            options={[
              { value: "", label: "Todas" },
              { value: "EMITIDA", label: "Emitida" },
              { value: "OBSERVADA", label: "Observada" },
              { value: "APROBADA", label: "Aprobada" },
              { value: "PAGADA", label: "Pagada" },
            ]}
          />
        </div>
      </Card>

      <ActionBar
        nuevo={{ onClick: () => {}, disabled: true, title: "No aplica: las liquidaciones se generan por lote, no una a una." }}
        actualizar={{ onClick: () => cargarLiquidaciones() }}
        eliminar={{ onClick: () => {}, disabled: true, title: "No aplica: las liquidaciones no se eliminan." }}
        buscar={{ onClick: () => cargarLiquidaciones() }}
        salir={{ onClick: limpiarBusquedaLiquidaciones }}
      />

      <Card>
        <h2 style={{ marginTop: 0, fontSize: "var(--font-size-lg)" }}>Liquidaciones</h2>
        <DataTable
          rows={liquidaciones}
          keyField={(l) => l.id}
          vacio="Todavía no se ha generado ninguna liquidación."
          columns={[
            { header: "Conductor", render: (l) => nombreConductor(l.conductor_id, l.conductor_nombre) },
            {
              header: "Periodo",
              render: (l) =>
                `${new Date(l.periodo_inicio).toLocaleDateString()} – ${new Date(l.periodo_fin).toLocaleDateString()}`,
            },
            {
              header: "Estado",
              render: (l) => (
                <Badge
                  texto={l.estado}
                  tono={
                    l.estado === "PAGADA"
                      ? "exito"
                      : l.estado === "APROBADA"
                        ? "neutral"
                        : l.estado === "OBSERVADA"
                          ? "peligro"
                          : "advertencia"
                  }
                />
              ),
            },
            { header: "Neto (en mano)", render: (l) => `$${l.neto.toFixed(2)}` },
            {
              header: "Saldo",
              render: (l) => <Badge texto={`$${l.saldo.toFixed(2)}`} tono={l.saldo < 0 ? "peligro" : "exito"} />,
            },
            {
              header: "Detalle",
              render: (l) => (
                <Button variant="secondary" onClick={() => abrirDetalleLiquidacion(l)}>
                  Ver
                </Button>
              ),
            },
          ]}
        />
        <Pagination
          page={pageLiq}
          pageSize={pageSizeLiq}
          total={totalLiquidaciones}
          onPageChange={setPageLiq}
          onPageSizeChange={(n) => {
            setPageSizeLiq(n);
            setPageLiq(0);
          }}
        />
      </Card>

      {liquidacionSeleccionada && (
        <DetailPanel
          titulo={`Liquidación — ${liquidacionSeleccionada.conductor_nombre ?? `conductor ${liquidacionSeleccionada.conductor_id.slice(0, 8)}…`}`}
          modo={modoLiq}
          onSalir={() => setLiquidacionSeleccionada(null)}
          onAceptar={
            liquidacionSeleccionada.estado === "EMITIDA"
              ? () => aprobarLiquidacion(liquidacionSeleccionada.id)
              : liquidacionSeleccionada.estado === "APROBADA"
                ? () => pagarLiquidacion(liquidacionSeleccionada.id)
                : liquidacionSeleccionada.estado === "OBSERVADA" && observacionEnRespuesta === liquidacionSeleccionada.id
                  ? () => responderObservacion(liquidacionSeleccionada.id, true)
                  : undefined
          }
          aceptarLabel={
            liquidacionSeleccionada.estado === "EMITIDA"
              ? "Aprobar"
              : liquidacionSeleccionada.estado === "APROBADA"
                ? "Confirmar pago"
                : "Ratificar"
          }
          aceptarLoading={accionando === liquidacionSeleccionada.id}
          aceptarDisabled={
            liquidacionSeleccionada.estado === "OBSERVADA" &&
            observacionEnRespuesta === liquidacionSeleccionada.id &&
            !respuestaMotivo.trim()
          }
          accionesExtra={
            liquidacionSeleccionada.estado === "OBSERVADA" && observacionEnRespuesta === liquidacionSeleccionada.id ? (
              <div style={{ minWidth: 140 }}>
                <Button
                  variant="danger"
                  onClick={() => responderObservacion(liquidacionSeleccionada.id, false)}
                  loading={accionando === liquidacionSeleccionada.id}
                  disabled={!respuestaMotivo.trim() || !ajusteMonto.trim()}
                >
                  Ajustar
                </Button>
              </div>
            ) : liquidacionSeleccionada.estado === "OBSERVADA" ? (
              <div style={{ minWidth: 180 }}>
                <Button variant="danger" onClick={() => setObservacionEnRespuesta(liquidacionSeleccionada.id)}>
                  Responder observación
                </Button>
              </div>
            ) : undefined
          }
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
            {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "var(--space-3)" }}>
              <DetailField
                label="Conductor"
                value={nombreConductor(liquidacionSeleccionada.conductor_id, liquidacionSeleccionada.conductor_nombre)}
              />
              <DetailField
                label="Periodo"
                value={`${new Date(liquidacionSeleccionada.periodo_inicio).toLocaleDateString()} – ${new Date(liquidacionSeleccionada.periodo_fin).toLocaleDateString()}`}
              />
              <DetailField
                label="Estado"
                value={
                  <Badge
                    texto={liquidacionSeleccionada.estado}
                    tono={
                      liquidacionSeleccionada.estado === "PAGADA"
                        ? "exito"
                        : liquidacionSeleccionada.estado === "APROBADA"
                          ? "neutral"
                          : liquidacionSeleccionada.estado === "OBSERVADA"
                            ? "peligro"
                            : "advertencia"
                    }
                  />
                }
              />
              <DetailField label="Bruto" value={`$${liquidacionSeleccionada.bruto.toFixed(2)}`} />
              <DetailField label="Comisiones" value={`$${liquidacionSeleccionada.comisiones.toFixed(2)}`} />
              <DetailField label="Ajustes" value={`$${liquidacionSeleccionada.ajustes.toFixed(2)}`} />
              <DetailField label="Neto (en mano)" value={`$${liquidacionSeleccionada.neto.toFixed(2)}`} />
              <DetailField label="Saldo" value={`$${liquidacionSeleccionada.saldo.toFixed(2)}`} />
              <DetailField label="Viajes incluidos" value={liquidacionSeleccionada.detalle.length} />
              {/* CU-O11 A1: el backend ya excluye del cálculo los viajes con
                  una discrepancia de pago sin resolver en el periodo — este
                  campo solo informa cuántos quedaron fuera, no aplica lógica
                  nueva. Se omite cuando es 0 para no ensuciar el detalle en
                  el caso normal. */}
              {liquidacionSeleccionada.viajes_en_revision > 0 && (
                <DetailField label="Viajes en revisión" value={`${liquidacionSeleccionada.viajes_en_revision} viajes en revisión`} />
              )}
            </div>

            {liquidacionSeleccionada.detalle.length > 0 && (
              <div>
                <h3 style={{ fontSize: "var(--font-size-md)" }}>Viajes de la liquidación</h3>
                <DataTable
                  rows={liquidacionSeleccionada.detalle}
                  keyField={(d) => d.viaje_id}
                  columns={[
                    { header: "Viaje", render: (d) => d.viaje_id },
                    { header: "Método", render: (d) => d.metodo },
                    { header: "Monto", render: (d) => `$${d.monto.toFixed(2)}` },
                    { header: "Comisión", render: (d) => `$${d.comision.toFixed(2)}` },
                    { header: "Neto socio", render: (d) => `$${d.neto_socio.toFixed(2)}` },
                    { header: "Fecha", render: (d) => new Date(d.ts).toLocaleString() },
                  ]}
                />
              </div>
            )}

            {liquidacionSeleccionada.estado === "OBSERVADA" && observacionEnRespuesta === liquidacionSeleccionada.id && (
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", borderTop: "1px solid var(--color-border)", paddingTop: "var(--space-3)" }}>
                {liquidacionSeleccionada.observacion_motivo && (
                  <p style={{ margin: 0, fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>
                    Motivo del socio: {liquidacionSeleccionada.observacion_motivo}
                  </p>
                )}
                <TextArea label="Motivo de la respuesta" value={respuestaMotivo} onChange={(e) => setRespuestaMotivo(e.target.value)} />
                <TextField
                  label="Monto de ajuste (solo si no se ratifica)"
                  type="number"
                  value={ajusteMonto}
                  onChange={(e) => setAjusteMonto(e.target.value)}
                />
              </div>
            )}
          </div>
        </DetailPanel>
      )}
    </div>
  );
}
