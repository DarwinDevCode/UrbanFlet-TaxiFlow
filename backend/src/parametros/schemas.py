from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ParametroTarifaCreate(BaseModel):
    franja: Literal["DIURNA", "NOCTURNA"]
    # Bitácora de revisión (2026-08-26, hallazgo #2): ningún monto de tarifa
    # tenía restricción de signo -- no hay pantalla que los edite todavía,
    # pero el endpoint ya aceptaba valores negativos vía API directa.
    arrancada: float = Field(ge=0)
    costo_km: float = Field(ge=0)
    costo_min_espera: float = Field(ge=0)
    carrera_minima: float = Field(ge=0)
    vigente_desde: datetime


class ParametroComisionCreate(BaseModel):
    # Se guarda como fracción 0-1 (`Comision.tsx` divide el % ingresado entre
    # 100 antes de enviarlo) -- 0% o 100%+ no son comisiones reales.
    porcentaje: float = Field(gt=0, le=1)
    vigente_desde: datetime


class ParametroOut(BaseModel):
    id: str
    tipo: Literal["tarifa", "comision"]
    valores: dict
    vigente_desde: datetime
    vigente_hasta: datetime | None
