from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

TipoOrden = Literal["PREVENTIVA", "CORRECTIVA"]
# Ronda 2, Fase E: ESPERANDO_REPUESTO -- estado intermedio nuevo entre
# EN_TALLER y CERRADA (CU-O12 A3: "espera visible de repuesto, con motivo").
# Transiciones válidas: ABIERTA -> EN_TALLER -> ESPERANDO_REPUESTO -> EN_TALLER
# (ida y vuelta), y CERRADA alcanzable desde EN_TALLER o ESPERANDO_REPUESTO.
EstadoOrden = Literal["ABIERTA", "EN_TALLER", "ESPERANDO_REPUESTO", "CERRADA", "ANULADA"]


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
    # Ronda 2, Fase G (punto 1): costo estimado vs. real -- la mano de obra
    # no tiene una lista de líneas como los repuestos, un único monto basta.
    mano_obra_estimada: float = Field(default=0.0, ge=0)


# Ronda 2, Fase G (punto 2, CU-O13 A1): orden CORRECTIVA nueva abierta al
# cerrar otra -- solo los campos que la orden encadenada no puede heredar
# del cierre en sí (tipo siempre CORRECTIVA por definición del caso de uso;
# km_entrada hereda km_salida de la orden que se está cerrando, es el mismo
# vehículo en el mismo instante, pedirlo de nuevo sería redundante).
class OrdenEncadenadaRequest(BaseModel):
    descripcion: str
    taller: str
    fecha_programada: date


class OrdenCerrarRequest(BaseModel):
    trabajos_realizados: str
    repuestos_consumidos: list[RepuestoInput] = Field(default_factory=list)
    costo_total: float = Field(gt=0)
    # Bitácora de revisión (2026-08-26, hallazgo #2): sin constraint hasta
    # ahora -- aceptaba horas negativas vía API aunque la UI nunca las
    # ofreciera a propósito.
    horas_taller: float | None = Field(default=None, ge=0)
    km_salida: int = Field(ge=0)
    habilitar_vehiculo: bool = False
    ajuste_justificado: bool = False
    motivo_ajuste: str | None = None
    orden_encadenada: OrdenEncadenadaRequest | None = None


class OrdenAnularRequest(BaseModel):
    motivo: str = Field(min_length=1)


# Ronda "corrección acotada por estado": qué campo es corregible depende del
# estado real de la orden (ver `service.py::corregir_orden` para el guard
# exacto) -- este único request cubre los 2 rangos:
# - ABIERTA: los 5 campos (nada se usó todavía, el vehículo ni siquiera
#   entró a taller).
# - EN_TALLER / ESPERANDO_REPUESTO: solo `repuestos_estimados`/
#   `mano_obra_estimada` -- `costo_estimado`/`desviacion_costo_pct` se
#   recalculan SIEMPRE en el momento del cierre a partir del valor VIGENTE
#   en ese instante (nunca se congelan antes), así que siguen siendo una
#   estimación de planificación corregible mientras la orden sigue abierta
#   en taller. `descripcion`/`taller`/`fecha_programada` quedan bloqueados
#   ahí: el vehículo ya está físicamente en ese taller trabajando sobre esa
#   descripción, y permitir mover `fecha_programada` después de que el
#   vehículo ya entró abriría la puerta a "corregir" retroactivamente el
#   plazo objetivo que mide `rpt_cumplimiento_plan_preventivo`.
class CorregirOrdenRequest(BaseModel):
    descripcion: str | None = Field(default=None, min_length=1)
    taller: str | None = None
    fecha_programada: date | None = None
    repuestos_estimados: list[RepuestoInput] | None = None
    mano_obra_estimada: float | None = Field(default=None, ge=0)
    motivo: str = Field(min_length=3)


# Ronda 2, Fase E (CU-O12 A3): motivo obligatorio y visible al pasar a espera
# de repuesto -- mismo criterio de "espera visible con motivo" que ya exige
# el ajuste justificado de km al cerrar (A3 de CU-O13).
class OrdenEsperaRepuestoRequest(BaseModel):
    motivo: str = Field(min_length=1)


# Ronda 2, Fase F: actividades embebidas -- bitácora propia de la orden
# (comentarios/avance del taller + transiciones automáticas relevantes),
# distinta de la bitácora global CU-O17 (esa sigue auditando las
# transiciones de estado en sí; esto es el detalle operativo legible para
# quien abre la orden). Insert-only, igual que `bitacora`.
TipoActividad = Literal["COMENTARIO", "CAMBIO_ESTADO"]


class ActividadOrdenOut(BaseModel):
    ts: datetime
    actor_id: str
    actor_nombre: str | None = None
    rol: str
    tipo: TipoActividad
    detalle: str
    evidencias: list[str] = Field(default_factory=list)


class ActividadCrearRequest(BaseModel):
    detalle: str = Field(min_length=1)
    evidencias: list[str] = Field(default_factory=list)


class VehiculoBusquedaOut(BaseModel):
    id: str
    placa: str
    marca: str
    modelo: str
    estado_habilitacion: str


# Decisión 3: baja lógica de un vehículo. Motivo obligatorio, mismo criterio
# que la baja de una cuenta y que el resto de acciones graves del sistema.
class VehiculoEditarRequest(BaseModel):
    """Solo datos descriptivos. `estado_habilitacion` y `propietario_id`
    quedan fuera a propósito -- ver `service.editar_vehiculo`."""

    placa: str | None = Field(default=None, min_length=3, max_length=15)
    marca: str | None = Field(default=None, min_length=1, max_length=60)
    modelo: str | None = Field(default=None, min_length=1, max_length=60)
    color: str | None = Field(default=None, min_length=1, max_length=40)
    anio: int | None = Field(default=None, ge=1950, le=2100)
    capacidad: int | None = Field(default=None, ge=1, le=20)


class BajaVehiculoRequest(BaseModel):
    motivo: str = Field(min_length=3)


class VehiculoBajaOut(BaseModel):
    id: str
    placa: str
    estado_habilitacion: str
    motivo_baja: str | None = None


# Ronda 2 (Fase B, H6/CU-O12 P1): ficha del vehículo con kilometraje real.
#
# Hallazgo real que corrige una premisa de la propuesta: no existe en el
# código NI en el modelo de datos ningún "plan preventivo por antigüedad del
# vehículo" -- la única referencia es el ejemplo de la spec ("cada 5 000 km",
# CU-O12 A2). No hay reglas diferenciadas por marca/modelo/año en ningún
# lado. Se implementa con un umbral GLOBAL único (`umbral_km_preventivo`,
# ver mantenimiento/service.py::UMBRAL_KM_PREVENTIVO) en vez de fabricar una
# diferenciación por antigüedad que ningún dato real respalda -- documentado
# explícitamente acá y en el servicio.
class FichaVehiculoOut(BaseModel):
    id: str
    placa: str
    marca: str
    modelo: str
    estado_habilitacion: str
    km_acumulado: float
    fecha_ultima_intervencion: datetime | None
    km_ultima_intervencion: int | None
    proxima_km_preventivo: float
    le_toca_preventivo: bool
    umbral_km_preventivo: int


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
    # Solo poblado en la respuesta de POST /ordenes/{id}/cierre (H9, CU-O13
    # P2) -- calculado a partir del km_salida recién registrado, no
    # persistido en la orden (es una proyección, no un hecho de la orden en
    # sí). `None` en cualquier otra respuesta de este mismo schema.
    proxima_km_preventivo: float | None = None
    # Ronda 2, Fase D: IDs de `archivos` (contexto "reporte_falla") heredados
    # al convertir un reporte de falla en orden -- vacío en toda orden creada
    # manualmente (patrón WorkPanel de siempre, sin evidencia de por medio).
    evidencias: list[str] = Field(default_factory=list)
    # Ronda 2, Fase E (CU-O12 A3): motivo de la espera de repuesto -- se
    # conserva como rastro histórico incluso después de reanudar (EN_TALLER
    # de nuevo), no se borra al volver.
    motivo_espera: str | None = None
    # Ronda 2, Fase F: cronológica (orden de inserción == orden de tiempo,
    # nunca se reordena en el servidor).
    actividades: list[ActividadOrdenOut] = Field(default_factory=list)
    # Ronda 2, Fase G (punto 1): costo estimado vs. real. `costo_estimado`
    # es una proyección calculada (mano_obra_estimada + suma de
    # repuestos_estimados), nunca persistida -- siempre presente (incluso
    # antes de cerrar, para que el panel de cierre lo muestre de entrada).
    # `desviacion_costo_pct` solo se puebla en la respuesta de POST /cierre
    # (mismo criterio que proxima_km_preventivo -- una comparación que solo
    # existe una vez que hay un costo_total real con qué comparar).
    mano_obra_estimada: float = 0.0
    costo_estimado: float = 0.0
    desviacion_costo_pct: float | None = None
    # Ronda 2, Fase G (punto 2): solo poblado en la respuesta de cierre
    # cuando se pidió abrir una orden encadenada -- id de la orden hija
    # recién creada.
    orden_encadenada_id: str | None = None


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
    registros_previos: dict[str, int | None] | None = None


class PanelEstadoCostoFlotaOut(BaseModel):
    kpis: EstadoCostoFlotaKpisOut
    tendencia_preventivo: list[PuntoPreventivoOut]
    tendencia_costo: list[PuntoCostoFlotaOut]
    candidatos_reemplazo: list[CandidatoReemplazoOut]
    metadata: EstadoCostoFlotaMetadataOut
