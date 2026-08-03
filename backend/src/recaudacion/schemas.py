from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

MetodoPago = Literal["EFECTIVO", "ELECTRONICO"]
EstadoPago = Literal["VALIDADO", "DISCREPANCIA", "PENDIENTE_CONFIRMACION"]


class RegistrarPagoRequest(BaseModel):
    viaje_id: str
    monto_cobrado: float = Field(ge=0)


class PagoOut(BaseModel):
    id: str
    viaje_id: str
    conductor_id: str
    conductor_nombre: str | None = None
    metodo: MetodoPago
    monto: float
    tarifa_final: float
    diferencia: float | None
    estado: EstadoPago
    referencia_externa: str | None
    ts_registro: datetime
    ts_confirmacion: datetime | None
    resuelto: bool = False
    resolucion_motivo: str | None = None
    resolucion_aceptado: bool | None = None
    resolucion_autorizador_id: str | None = None
    resolucion_ts: datetime | None = None


class ViajeSinPagoOut(BaseModel):
    viaje_id: str
    conductor_id: str
    conductor_nombre: str | None = None
    tarifa_final: float
    ts_fin: datetime


class BandejaDiscrepanciasOut(BaseModel):
    discrepancias: list[PagoOut]
    viajes_sin_pago: list[ViajeSinPagoOut]


class ResolverDiscrepanciaRequest(BaseModel):
    aceptar: bool
    motivo: str


class CrearAjusteRequest(BaseModel):
    monto: float
    motivo: str = Field(min_length=1)


class MovimientoOut(BaseModel):
    id: str
    viaje_id: str | None
    tipo: Literal["COMISION", "NETO_SOCIO", "AJUSTE"]
    monto_firmado: float
    comision_version_id: str | None
    motivo: str | None
    autorizador_id: str | None
    ts: datetime
    liquidacion_id: str | None


EstadoLiquidacion = Literal["EMITIDA", "OBSERVADA", "APROBADA", "PAGADA"]


class LiquidacionDetalleViajeOut(BaseModel):
    viaje_id: str
    metodo: MetodoPago
    monto: float
    comision: float
    neto_socio: float
    ts: datetime


class LiquidacionOut(BaseModel):
    id: str
    conductor_id: str
    conductor_nombre: str | None = None
    periodo_inicio: datetime
    periodo_fin: datetime
    estado: EstadoLiquidacion
    bruto: float
    comisiones: float
    ajustes: float
    neto: float
    saldo: float
    detalle: list[LiquidacionDetalleViajeOut]
    ts_emision: datetime
    ts_aprobacion: datetime | None
    ts_pago: datetime | None
    aprobador_id: str | None
    observacion_motivo: str | None = None
    observacion_ts: datetime | None = None
    viajes_en_revision: int = 0


class GenerarLiquidacionesResponse(BaseModel):
    periodo_inicio: datetime
    periodo_fin: datetime
    generadas: list[LiquidacionOut]
    ya_existian: list[str]


class ObservarLiquidacionRequest(BaseModel):
    motivo: str


class ResponderObservacionRequest(BaseModel):
    ratificar: bool
    motivo: str
    ajuste_monto: float | None = None


class AlertaSaldoNegativoOut(BaseModel):
    conductor_id: str
    conductor_nombre: str | None = None
    periodos_consecutivos: int
    liquidaciones: list[LiquidacionOut]


class LiquidacionListOut(BaseModel):
    items: list[LiquidacionOut]
    total: int


class TasaDiscrepanciasOut(BaseModel):
    """Fila del informe compuesto (ClickHouse) `rpt_tasa_discrepancias` -- CU-T09/OT5.1."""

    fecha_periodo: date
    metodo: str
    pct_discrepancia: float
    pct_conciliado: float
    total_registros: int


class MargenComisionOut(BaseModel):
    """Fila del informe compuesto (ClickHouse) `rpt_margen_comision` -- CU-T12/OT5.2."""

    periodo: str
    margen: float
    bruto_total: float
    comisiones_total: float
    horas_hasta_pago_promedio: float | None
