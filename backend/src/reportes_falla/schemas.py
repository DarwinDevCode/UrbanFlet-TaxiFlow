from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from src.mantenimiento.schemas import RepuestoInput

EstadoReporteFalla = Literal["PENDIENTE", "CONVERTIDO_A_ORDEN", "DESCARTADO"]


class ReportarFallaRequest(BaseModel):
    # Nombre del catálogo `motivos` (categoría "incidencia", Ronda 1) --
    # texto libre validado contra el catálogo en el service, mismo criterio
    # que `viajes.motivo_cancelacion` (nunca se migró a FK, ver
    # catalogos/service.py).
    tipo_falla: str
    descripcion: str = Field(min_length=1)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    impide_continuar: bool = False
    # IDs de `archivos` ya subidos vía POST /archivos (contexto
    # "reporte_falla") antes de enviar este formulario.
    evidencias: list[str] = Field(default_factory=list)


class ReportarFallaStaffRequest(BaseModel):
    """Variante de `ReportarFallaRequest` para personal interno
    (`jefe_mantenimiento`) creando el reporte desde `web-interno` en vez del
    conductor desde su app. El vehículo se elige explícitamente (no se infiere
    de un conductor propietario); sin `impide_continuar` ni `lat`/`lon` -- no
    hay viaje de por medio ni geolocalización de un dispositivo móvil en este
    contexto, ver `reportes_falla/service.py::crear_reporte_falla_staff`."""

    vehiculo_id: str
    tipo_falla: str
    descripcion: str = Field(min_length=1)
    evidencias: list[str] = Field(default_factory=list)


class ReporteFallaOut(BaseModel):
    id: str
    vehiculo_id: str
    vehiculo_placa: str | None = None
    conductor_id: str
    viaje_id: str | None
    tipo_falla: str
    descripcion: str
    lat: float
    lon: float
    ts: datetime
    impide_continuar: bool
    estado: EstadoReporteFalla
    orden_id: str | None
    evidencias: list[str]
    motivo_descarte: str | None = None


class DescartarReporteRequest(BaseModel):
    motivo: str = Field(min_length=1)


# Ronda "corrección acotada por estado": solo mientras el reporte sigue
# PENDIENTE (ver `service.py::corregir_reporte`, que reusa `_reporte_pendiente`
# para bloquear fuera de ese estado). `vehiculo_id` e `impide_continuar`
# quedan fuera a propósito -- ver el resumen de esa ronda para el análisis
# completo campo por campo.
class CorregirReporteRequest(BaseModel):
    tipo_falla: str | None = None
    descripcion: str | None = Field(default=None, min_length=1)
    motivo: str = Field(min_length=3)


# Ronda 2, Fase D: "Convertir en orden" -- la propuesta pide reusar el
# selector de taller de la Ronda 1 tal cual, no reconstruirlo; los campos de
# abajo son exactamente los que `OrdenCrearRequest` necesita y que un reporte
# de falla NO trae por sí solo (taller/fecha/km de entrada los decide el
# Jefe de Mantenimiento en este paso, no el conductor al reportar).
class ConvertirReporteRequest(BaseModel):
    taller: str
    fecha_programada: date
    km_entrada: int = Field(ge=0)
    retirar_vehiculo: bool = False
    repuestos_estimados: list[RepuestoInput] = Field(default_factory=list)
