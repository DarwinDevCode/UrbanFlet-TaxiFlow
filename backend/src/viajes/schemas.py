from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

EstadoViaje = Literal[
    "PROGRAMADO",
    "SOLICITADO",
    "OFERTADO",
    "ASIGNADO",
    "EN_CAMINO",
    "EN_CURSO",
    "FINALIZADO",
    "PAGADO",
    "CANCELADO",
    "SIN_CONDUCTOR",
]
Franja = Literal["DIURNA", "NOCTURNA"]


class SolicitarViajeRequest(BaseModel):
    origen_lat: float = Field(ge=-90, le=90)
    origen_lon: float = Field(ge=-180, le=180)
    origen_direccion: str
    destino_lat: float | None = Field(default=None, ge=-90, le=90)
    destino_lon: float | None = Field(default=None, ge=-180, le=180)
    destino_direccion: str | None = None
    # Sección 1.5 de ux_complementaria.md: "Ahora" (None, comportamiento de
    # siempre) vs. "Programar" (hora futura -- el viaje se crea en
    # PROGRAMADO y el auto-despacho se dispara después, cerca de esa hora).
    ts_programado: datetime | None = None


class CalificacionOut(BaseModel):
    puntaje: int
    comentario: str | None
    ts: datetime


class ViajeOut(BaseModel):
    id: str
    pasajero_id: str
    conductor_id: str | None
    vehiculo_id: str | None
    estado: EstadoViaje
    origen_lat: float
    origen_lon: float
    origen_direccion: str
    destino_lat: float | None
    destino_lon: float | None
    destino_direccion: str | None
    franja: Franja
    ts_programado: datetime | None = None
    ts_solicitud: datetime
    ts_asignacion: datetime | None
    ts_llegada_origen: datetime | None = None
    ts_inicio: datetime | None
    ts_fin: datetime | None
    km_recorridos: float | None
    min_espera: float | None
    tarifa_estimada: float | None
    tarifa_final: float | None
    motivo_cancelacion: str | None
    conductor_nombre: str | None = None
    conductor_calificacion: float | None = None
    # Sección 2.2 de la spec ux_complementaria.md: foto que el pasajero ve
    # al ser asignado (CU-O05 P5), editable por el conductor en "Mi perfil".
    conductor_foto_url: str | None = None
    vehiculo_placa: str | None = None
    vehiculo_marca: str | None = None
    vehiculo_color: str | None = None
    calificacion_pasajero_a_conductor: CalificacionOut | None = None
    calificacion_conductor_a_pasajero: CalificacionOut | None = None
    # CU-O14 paso 3 / A2: "datos de la contraparte (limitados: nombre y
    # calificación)" — para cuando el CONDUCTOR consulta el historial, ya que
    # conductor_nombre/conductor_calificacion (arriba) cubren el caso inverso
    # (pasajero viendo al conductor) desde que se asigna el viaje. Nunca
    # incluye teléfono ni historial de ubicaciones del pasajero.
    pasajero_nombre: str | None = None
    pasajero_calificacion: float | None = None


class HistorialOut(BaseModel):
    viajes: list[ViajeOut]
    total: int
    pagina: int
    limite: int


# Sección 1.2 de ux_complementaria.md: compartir viaje en tiempo real.
class CompartirViajeOut(BaseModel):
    token: str


class PosicionCompartidaOut(BaseModel):
    lat: float
    lon: float


class ViajeCompartidoOut(BaseModel):
    """Salida del endpoint público `GET /publico/viajes-compartidos/{token}`
    -- deliberadamente mínima: nunca teléfono/correo, nunca datos del
    pasajero (quien lo generó ya sabe quién es), solo lo que un contacto de
    confianza necesita para verificar que el viaje va bien."""

    conductor_nombre: str | None
    conductor_calificacion: float | None
    conductor_foto_url: str | None
    vehiculo_placa: str | None
    estado: EstadoViaje
    posicion: PosicionCompartidaOut | None


class CalificarViajeRequest(BaseModel):
    puntaje: int = Field(ge=1, le=5)
    comentario: str | None = None


class OfertaActualOut(BaseModel):
    viaje_id: str
    pasajero_nombre: str
    pasajero_calificacion: float | None
    origen_lat: float
    origen_lon: float
    distancia_km: float | None
    tiene_destino: bool
    segundos_restantes: int


class ResponderOfertaRequest(BaseModel):
    aceptar: bool


class EstimacionRutaOut(BaseModel):
    # Directions API de Google no envía cabeceras CORS — la ruta se pide
    # siempre a través del backend, nunca directo desde el navegador (ver
    # rutas.ts en web-pasajero). `origen_directions=False` indica que se usó
    # el respaldo de línea recta (cuota agotada, sin ruta, red caída, etc.).
    ruta: list[tuple[float, float]]
    distancia_km: float
    duracion_min: float
    origen_directions: bool


class ViajeActivoOut(BaseModel):
    """Panel táctico de Despacho -- CU-T07, informe simple (MongoDB)."""

    id: str
    pasajero_id: str
    conductor_id: str | None
    estado: EstadoViaje
    zona_origen_id: str | None = None
    ts_solicitud: datetime


class ViajeSinConductorCanceladoOut(BaseModel):
    """Panel táctico de Despacho -- CU-T08, informe simple (MongoDB)."""

    id: str
    estado: EstadoViaje
    motivo_cancelacion: str | None
    actor_cancelacion: str | None = None
    ts_solicitud: datetime


class TiempoAsignacionOut(BaseModel):
    """Fila del informe compuesto (ClickHouse) `rpt_tiempo_asignacion` -- CU-T07/OT4.1."""

    zona_origen_id: str
    franja: str
    segundos_promedio: float
    segundos_p95: float
    total_registros: int


class TasaCancelacionOut(BaseModel):
    """Fila del informe compuesto (ClickHouse) `rpt_tasa_cancelacion` -- CU-T08/OT4.2."""

    periodo: str
    zona_origen_id: str
    motivo: str
    actor: str
    cancelados: int
    solicitados: int
    tasa_cancelacion: float


# ---------------------------------------------------------------------------
# Nivel estratégico — Panel de Confiabilidad y Disponibilidad (OE2a)
# ---------------------------------------------------------------------------


class ConfiabilidadKpisOut(BaseModel):
    segundos_asignacion_promedio: float | None
    cancelaciones_periodo: int | None
    variacion_cancelaciones_pct: float | None
    # Siempre `None`: `rpt_tasa_cancelacion` solo publica filas de viajes ya
    # cancelados (`HAVING cancelados > 0`), así que no tiene denominador real
    # para una tasa. Ver el docstring de `service.obtener_panel_confiabilidad`.
    tasa_cancelacion: float | None = None
    pct_flota_activa: float | None
    franja_menor_cobertura: str | None


class PuntoAsignacionOut(BaseModel):
    periodo: str
    segundos_promedio: float
    total_registros: int


class PuntoCancelacionOut(BaseModel):
    periodo: str
    cancelados: int
    sin_conductor: int


class PuntoFlotaOut(BaseModel):
    periodo: str
    pct_disponible: float
    total_registros: int


class FranjaCoberturaOut(BaseModel):
    franja: str
    pct_disponible: float
    total_registros: int


class FranjaAsignacionOut(BaseModel):
    """Franja según la taxonomía de `rpt_tiempo_asignacion` (DIURNA/NOCTURNA),
    distinta de la de `rpt_flota_activa_franja` (00-06/06-12/...) — por eso
    va en su propia lista y no cruzada con `FranjaCoberturaOut`."""

    franja: str
    segundos_promedio: float
    total_registros: int


class ConfiabilidadMetadataOut(BaseModel):
    meses: int
    # `false` mientras `viajes.zona_origen_id` siga sin resolverse: el futuro
    # frontend usa esta bandera para mostrar la limitación en vez de un filtro
    # de zona que no filtraría nada.
    zona_disponible: bool
    tasa_cancelacion_disponible: bool
    fuentes: list[str]


class PanelConfiabilidadOut(BaseModel):
    kpis: ConfiabilidadKpisOut
    tendencia_asignacion: list[PuntoAsignacionOut]
    tendencia_cancelacion: list[PuntoCancelacionOut]
    tendencia_flota: list[PuntoFlotaOut]
    franjas: list[FranjaCoberturaOut]
    franjas_asignacion: list[FranjaAsignacionOut]
    metadata: ConfiabilidadMetadataOut
