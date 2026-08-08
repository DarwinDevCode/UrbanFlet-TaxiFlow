from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

TipoOrden = Literal["PREVENTIVA", "CORRECTIVA"]
EstadoOrden = Literal["ABIERTA", "EN_TALLER", "CERRADA", "ANULADA"]


class RepuestoInput(BaseModel):
    descripcion: str
    cantidad: int = Field(gt=0)
    costo_unitario: float = Field(ge=0)


class OrdenCrearRequest(BaseModel):
    vehiculo_id: str
    tipo: TipoOrden
    descripcion: str
    km_entrada: int = Field(ge=0)
    taller: str
    fecha_programada: date
    retirar_vehiculo: bool = False
    repuestos_estimados: list[RepuestoInput] = Field(default_factory=list)


class OrdenCerrarRequest(BaseModel):
    trabajos_realizados: str
    repuestos_consumidos: list[RepuestoInput] = Field(default_factory=list)
    costo_total: float = Field(gt=0)
    horas_taller: float | None = None
    km_salida: int = Field(ge=0)
    habilitar_vehiculo: bool = False
    ajuste_justificado: bool = False
    motivo_ajuste: str | None = None


class OrdenAnularRequest(BaseModel):
    motivo: str = Field(min_length=1)


class VehiculoBusquedaOut(BaseModel):
    id: str
    placa: str
    marca: str
    modelo: str
    estado_habilitacion: str


class OrdenOut(BaseModel):
    id: str
    vehiculo_id: str
    vehiculo_placa: str | None = None
    tipo: TipoOrden
    estado: EstadoOrden
    descripcion: str
    km_entrada: int
    km_salida: int | None
    taller: str
    fecha_programada: date
    fecha_cierre: datetime | None
    costo_total: float | None
    orden_madre_id: str | None
    repuestos_estimados: list[RepuestoInput] = Field(default_factory=list)
    repuestos_consumidos: list[RepuestoInput] = Field(default_factory=list)
    horas_taller: float | None = None


class OrdenListOut(BaseModel):
    items: list[OrdenOut]
    total: int


class VehiculoRetiradoOut(BaseModel):
    """Panel táctico -- CU-T04/OT7.1: vehículo `RETIRADO_DE_SERVICIO` y la orden que lo retiene."""

    vehiculo_id: str
    placa: str
    orden_id: str | None = None
    orden_estado: EstadoOrden | None = None
    fecha_programada: date | None = None


class CumplimientoPreventivoOut(BaseModel):
    """Fila del informe compuesto (ClickHouse) `rpt_cumplimiento_plan_preventivo` -- CU-T04/OT7.1."""

    periodo: str
    pct_cumplimiento: float
    total_ordenes: int


class CostoMantenimientoVehiculoOut(BaseModel):
    """Fila del informe compuesto (ClickHouse) `rpt_costo_mantenimiento_vehiculo` -- CU-T11/OT7.2."""

    vehiculo_id: str
    vehiculo_placa: str | None = None
    periodo: str
    costo_total: float
    total_ordenes: int


# ---------------------------------------------------------------------------
# Nivel estratégico — Panel de Estado y Costo de Flota (OE2b)
# ---------------------------------------------------------------------------


class EstadoCostoFlotaKpisOut(BaseModel):
    pct_cumplimiento_preventivo: float | None
    variacion_cumplimiento_pct: float | None
    costo_mantenimiento_periodo: float | None
    variacion_costo_pct: float | None
    costo_acumulado: float | None


class PuntoPreventivoOut(BaseModel):
    periodo: str
    pct_cumplimiento: float
    total_ordenes: int


class PuntoCostoFlotaOut(BaseModel):
    periodo: str
    costo_total: float
    total_ordenes: int


class CandidatoReemplazoOut(BaseModel):
    vehiculo_id: str
    vehiculo_placa: str | None = None
    costo_total: float
    costo_promedio_mes: float | None = None
    total_ordenes: int
    periodos: int
    # Siempre `None`: el kilometraje no existe en ninguna vista `rpt_*` y la
    # spec estratégica prohíbe leerlo de Mongo. Ver `metadata.km_disponible`.
    km_recorridos: float | None = None


class EstadoCostoFlotaMetadataOut(BaseModel):
    meses: int
    km_disponible: bool
    fuentes: list[str]


class PanelEstadoCostoFlotaOut(BaseModel):
    kpis: EstadoCostoFlotaKpisOut
    tendencia_preventivo: list[PuntoPreventivoOut]
    tendencia_costo: list[PuntoCostoFlotaOut]
    candidatos_reemplazo: list[CandidatoReemplazoOut]
    metadata: EstadoCostoFlotaMetadataOut
