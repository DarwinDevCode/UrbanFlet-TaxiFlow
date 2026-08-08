from datetime import date, datetime

from pydantic import BaseModel


class InformeOut(BaseModel):
    """Un informe táctico publicado por CU-O16 (analytics/plugins/indicadores.py).

    `filas` es intencionalmente `list[dict]` -- cada informe tiene columnas
    propias (franja/pct_disponible, tipo/canal/pct_activo, etc.) y no hay
    ganancia en modelar 6 schemas distintos para datos que el frontend
    consume genéricamente como tabla. `datos_al`/`retrasado` sí son
    contractuales para todos: son el corazón de CU-O16 (A1: aviso de
    retraso cuando la corrida del dominio falló)."""

    id: str
    nombre: str
    datos_al: date | None
    retrasado: bool
    filas: list[dict]


class CatalogoIndicadoresOut(BaseModel):
    informes: list[InformeOut]


class CorridaOut(BaseModel):
    """Panel táctico de Plataforma -- CU-T14/OT8.1, informe simple.

    Decisión del usuario: se sirve desde ClickHouse (tabla `corridas`, ya
    real) en vez de la colección Mongo `corridas_etl` que pide el spec --
    esa colección no existe, el seguimiento de corridas del pipeline vive en
    ClickHouse desde el principio (analytics/plugins/medallion.py)."""

    dag_id: str
    fecha_logica: date
    estado: str
    registros_extraidos: int
    registros_cuarentena: int
    pct_cuarentena: float
    iniciado_en: datetime
    finalizado_en: datetime | None


class CuarentenaDominioOut(BaseModel):
    """Fila del informe compuesto (ClickHouse) `rpt_cuarentena_dominio` -- CU-T14/OT8.1."""

    dag_id: str
    pct_cuarentena: float
    registros_extraidos: int
    registros_cuarentena: int


# ---------------------------------------------------------------------------
# Nivel estratégico — Panel de Capacidades y Plataforma (OE3)
# ---------------------------------------------------------------------------


class CapacidadesKpisOut(BaseModel):
    pct_cuarentena_global: float | None
    variacion_cuarentena_pct: float | None
    dominio_mas_afectado: str | None
    corridas_ok: int
    corridas_fallidas: int
    # Siempre `None`: no existe dominio de capacitación en el sistema
    # (backlog consciente ya declarado en el nivel táctico).
    avance_capacitacion_pct: float | None = None


class PuntoCuarentenaOut(BaseModel):
    periodo: str
    pct_cuarentena: float
    registros_extraidos: int
    registros_cuarentena: int


class DominioCuarentenaOut(BaseModel):
    dag_id: str
    pct_cuarentena: float
    registros_extraidos: int
    registros_cuarentena: int


class CapacidadesMetadataOut(BaseModel):
    cortes: int
    capacitacion_disponible: bool
    fuentes: list[str]


class PanelCapacidadesOut(BaseModel):
    kpis: CapacidadesKpisOut
    tendencia_cuarentena: list[PuntoCuarentenaOut]
    dominios: list[DominioCuarentenaOut]
    metadata: CapacidadesMetadataOut
