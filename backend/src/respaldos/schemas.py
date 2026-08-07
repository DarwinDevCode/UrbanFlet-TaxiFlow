from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Motor = Literal["mongo", "clickhouse"]
EstadoRespaldo = Literal["en_progreso", "completado", "error"]


class RespaldoOut(BaseModel):
    id: str
    motor: Motor
    estado: EstadoRespaldo
    ts_inicio: datetime
    ts_fin: datetime | None
    duracion_segundos: float | None
    tamano_bytes: int | None
    hash_sha256: str | None
    colecciones: list[str] | None
    error_detalle: str | None
    disparado_por: str


class VerificacionOut(BaseModel):
    id: str
    integro: bool
    hash_esperado: str
    hash_calculado: str


class RestauracionOut(BaseModel):
    id: str
    respaldo_id: str
    motor: Motor
    estado: EstadoRespaldo
    base_destino: str
    ts_inicio: datetime
    ts_fin: datetime | None
    duracion_segundos: float | None
    conteos: dict[str, int] | None
    error_detalle: str | None


# Módulo 7.2 — Plan de continuidad (DR)
DominioDr = Literal[
    "captacion", "operaciones_despacho", "flota", "mantenimiento", "finanzas", "cumplimiento", "plataforma"
]


class PlanDrItem(BaseModel):
    dominio: DominioDr
    rto: str
    rpo: str
    notas: str
    actualizado_en: datetime | None
    actualizado_por: str | None


class PlanDrActualizar(BaseModel):
    rto: str = Field(min_length=1, max_length=200)
    rpo: str = Field(min_length=1, max_length=200)
    notas: str = Field(default="", max_length=1000)


class SimulacroCreate(BaseModel):
    fecha: datetime
    resultado: Literal["exitoso", "parcial", "fallido"]
    notas: str = Field(min_length=1, max_length=2000)


class SimulacroOut(BaseModel):
    id: str
    fecha: datetime
    resultado: str
    notas: str
    registrado_por: str
    registrado_en: datetime
