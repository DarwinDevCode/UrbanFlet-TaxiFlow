from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ParametroTarifaCreate(BaseModel):
    franja: Literal["DIURNA", "NOCTURNA"]
    arrancada: float
    costo_km: float
    costo_min_espera: float
    carrera_minima: float
    vigente_desde: datetime


class ParametroComisionCreate(BaseModel):
    porcentaje: float
    vigente_desde: datetime


class ParametroOut(BaseModel):
    id: str
    tipo: Literal["tarifa", "comision"]
    valores: dict
    vigente_desde: datetime
    vigente_hasta: datetime | None


class ZonaCreate(BaseModel):
    nombre: str
    geometria: dict


class ZonaOut(BaseModel):
    id: str
    nombre: str
    geometria: dict
