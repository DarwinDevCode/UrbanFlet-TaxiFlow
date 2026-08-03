from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

EstadoServicio = Literal["FUERA_DE_LINEA", "DISPONIBLE", "OCUPADO", "SIN_SEÑAL"]


class PosicionReportarRequest(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    precision_m: float = Field(ge=0)
    # km/h — la Geolocation API del navegador entrega m/s; la conversión es
    # responsabilidad del cliente antes de enviar (ver web-conductor/src/App.tsx).
    velocidad: float | None = None
    rumbo: float | None = None
    ts_dispositivo: datetime


class PosicionReportarResponse(BaseModel):
    aceptada: bool
    precision_baja: bool = False
    motivo_descarte: str | None = None


class TurnoOut(BaseModel):
    estado_servicio: EstadoServicio


class VehiculoEstadoOut(BaseModel):
    vehiculo_id: str
    vehiculo_placa: str | None = None
    conductor_id: str
    conductor_nombre: str | None = None
    estado_servicio: EstadoServicio
    lat: float | None
    lon: float | None
    ts_servidor: datetime | None
    sin_senal: bool


class VehiculoCercanoOut(BaseModel):
    """CU-O04 P1: "íconos anónimos" — deliberadamente sin conductor_id,
    vehiculo_id ni ningún otro dato identificable, solo la posición para
    dibujar un marcador genérico en el mapa del pasajero."""

    lat: float
    lon: float


class FlotaActivaFranjaOut(BaseModel):
    """Fila del informe compuesto (ClickHouse) `rpt_flota_activa_franja` -- CU-T05/OT3.2."""

    franja: str
    pct_disponible: float
    total_registros: int


class PosicionConductorOut(BaseModel):
    """Posición conocida de un conductor puntual — a diferencia de
    VehiculoCercanoOut, esto SÍ identifica al conductor por su id en la ruta
    (nunca se expone en el cuerpo), porque solo se entrega a quien ya tiene
    autorización explícita para verlo: el propio conductor, o el pasajero de
    un viaje que ese conductor tiene asignado en este momento (ver
    service.obtener_posicion_conductor)."""

    lat: float
    lon: float
    ts_servidor: datetime
