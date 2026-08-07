from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Componente = Literal["backend", "web-pasajero", "web-conductor", "web-interno", "todos"]

ComponenteMonitoreo = Literal["backend", "mongo", "redis", "clickhouse", "airflow"]


class VersionOut(BaseModel):
    backend: str
    web_pasajero: str
    web_conductor: str
    web_interno: str


class DespliegueCreate(BaseModel):
    componente: Componente
    version: str = Field(min_length=1, max_length=50)
    notas: str = Field(default="", max_length=500)


class DespliegueOut(BaseModel):
    id: str
    componente: Componente
    version: str
    notas: str
    desplegado_en: datetime
    desplegado_por: str | None


class SaludComponenteOut(BaseModel):
    componente: ComponenteMonitoreo
    disponible: bool
    latencia_ms: float | None
    estado: Literal["bien", "advertencia", "critico"]


class UmbralOut(BaseModel):
    componente: ComponenteMonitoreo
    latencia_advertencia_ms: int
    latencia_critica_ms: int


class UmbralActualizar(BaseModel):
    latencia_advertencia_ms: int = Field(ge=1, le=60000)
    latencia_critica_ms: int = Field(ge=1, le=60000)


class PoliticaRetencionItem(BaseModel):
    coleccion: str
    descripcion: str
    retencion: str
    fuente: Literal["indice_ttl_real", "documentado"]


# Punto #6 de la ronda de usabilidad post-cierre (2026-08-07): indicadores
# reales de infraestructura (no solo disponibilidad/latencia) vía los
# drivers ya en uso -- serverStatus/dbStats (Mongo), INFO (Redis),
# system.metrics/system.asynchronous_metrics (ClickHouse). Sin Airflow por
# ahora (aprobado explícitamente, queda para una sesión aparte).
class IndicadorMongo(BaseModel):
    disponible: bool
    conexiones_activas: int | None = None
    conexiones_disponibles: int | None = None
    operaciones_totales: int | None = None
    tamano_datos_mb: float | None = None
    tamano_almacenamiento_mb: float | None = None
    colecciones: int | None = None
    indices: int | None = None
    tiempo_actividad_seg: int | None = None


class IndicadorRedis(BaseModel):
    disponible: bool
    memoria_usada_mb: float | None = None
    clientes_conectados: int | None = None
    hit_rate_pct: float | None = None
    tiempo_actividad_seg: int | None = None


class IndicadorClickhouse(BaseModel):
    disponible: bool
    consultas_activas: int | None = None
    memoria_usada_mb: float | None = None
    tiempo_actividad_seg: int | None = None


class IndicadoresOut(BaseModel):
    mongo: IndicadorMongo
    redis: IndicadorRedis
    clickhouse: IndicadorClickhouse


class HistorialLatenciaPunto(BaseModel):
    ts: datetime
    componente: ComponenteMonitoreo
    latencia_ms: float | None
    estado: Literal["bien", "advertencia", "critico"]
