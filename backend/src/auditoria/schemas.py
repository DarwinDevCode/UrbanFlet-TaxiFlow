from datetime import datetime
from typing import Any

from pydantic import BaseModel


class EventoAuditoriaOut(BaseModel):
    evento_id: int
    ts: datetime
    actor_id: str | None
    rol: str | None
    accion: str
    entidad: str
    entidad_id: str | None
    resultado: str
    ip: str | None
    dispositivo: str | None
    # Módulo 6.1 de admin_sistema: "comparación antes/después" -- estos dos
    # campos ya existían en EVENTO_AUDITORIA (core/audit.py), simplemente
    # nunca se habían expuesto en la API de lectura porque ningún consumidor
    # los necesitaba todavía.
    datos_previos: dict[str, Any] | None = None
    datos_posteriores: dict[str, Any] | None = None


class EventosPage(BaseModel):
    items: list[EventoAuditoriaOut]
    total: int
    pagina: int
    tamanio_pagina: int


class UsoIntegracionOut(BaseModel):
    """Fila del informe compuesto (ClickHouse) `rpt_uso_integraciones` -- CU-T03/OT2.1.

    Simplificado: solo conteo de solicitudes por endpoint (derivado de la
    bitácora de auditoría) -- no hay dominio de credenciales de API en el
    sistema, así que "por credencial" y latencia/tasa de error quedan fuera
    de alcance (backlog consciente, decisión explícita del usuario)."""

    endpoint: str
    conteo: int
    total_global: int


# --------------------------------------------------------------------------
# Nivel estratégico — Panel de Gobernanza de Datos y Seguridad (OE6b/CU-E05)
# --------------------------------------------------------------------------


class GobernanzaKpisOut(BaseModel):
    eventos_administrativos: int
    accesos_denegados: int
    alertas_seguridad: int
    # Variación del conteo de accesos denegados contra la ventana previa de
    # igual longitud. `None` cuando la ventana previa no tiene ningún evento
    # (división por cero) -- se devuelve nulo en vez de fabricar un 0%.
    variacion_accesos_denegados_pct: float | None = None


class GobernanzaTendenciaOut(BaseModel):
    periodo: str
    eventos_administrativos: int
    accesos_denegados: int
    alertas_seguridad: int


class GobernanzaMetadataOut(BaseModel):
    meses: int
    desde: datetime
    fuente: str
    registros_previos: dict[str, int | None] | None = None


class PanelGobernanzaOut(BaseModel):
    kpis: GobernanzaKpisOut
    tendencia: list[GobernanzaTendenciaOut]
    eventos: list[EventoAuditoriaOut]
    metadata: GobernanzaMetadataOut
