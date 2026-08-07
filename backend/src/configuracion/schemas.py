from datetime import datetime

from pydantic import BaseModel, Field


class ParametroSistemaCreate(BaseModel):
    idioma: str = Field(min_length=2, max_length=10)
    zona_horaria: str = Field(min_length=1, max_length=64)
    # Primer elemento = radio inicial de despacho; los siguientes son las
    # ampliaciones sucesivas si no aparece candidato (CU-O05 A1/A2). Mismo
    # dato que hoy vive fijo en `viajes/service_dispatch.py::RADIOS_M`.
    radios_despacho_m: list[int] = Field(min_length=1, max_length=10)
    oferta_expira_segundos: int = Field(ge=5, le=300)
    vigente_desde: datetime


class ParametroSistemaOut(BaseModel):
    id: str | None
    idioma: str
    zona_horaria: str
    radios_despacho_m: list[int]
    oferta_expira_segundos: int
    vigente_desde: datetime | None
    vigente_hasta: datetime | None


class FlagCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    activo: bool = False
    porcentaje: int | None = Field(default=None, ge=0, le=100)
    roles: list[str] | None = None


class FlagActualizar(BaseModel):
    activo: bool | None = None
    porcentaje: int | None = Field(default=None, ge=0, le=100)
    roles: list[str] | None = None


class FlagOut(BaseModel):
    id: str
    nombre: str
    activo: bool
    porcentaje: int | None
    roles: list[str]
    creado_en: datetime
    actualizado_en: datetime
