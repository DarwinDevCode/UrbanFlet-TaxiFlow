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
