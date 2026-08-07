from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

TipoAlerta = Literal["denegaciones_rbac", "gps_spoofing", "pipeline_fallido"]


class ConfiguracionAlertaOut(BaseModel):
    tipo_alerta: TipoAlerta
    canal: Literal["web_push"]
    destinatarios_adicionales: list[str]
    activo: bool
    rol_destinatario_default: str
    actualizado_en: datetime | None


class ConfiguracionAlertaActualizar(BaseModel):
    # Único canal con entrega real hoy (ver `notificaciones/service.py` --
    # no hay envío de correo en el codebase). No se acepta "correo"/"ambos"
    # como valor -- sería un selector que promete algo que no ocurre.
    canal: Literal["web_push"] = "web_push"
    destinatarios_adicionales: list[str] = Field(default_factory=list)
    activo: bool = True


# Sección 4.2 de ux_complementaria.md: bandeja in-app, autoservicio de
# cualquier actor autenticado sobre sus propias notificaciones.
class NotificacionOut(BaseModel):
    id: str
    tipo: str
    categoria: str
    payload: dict
    ts: datetime
    leida: bool


class NotificacionListOut(BaseModel):
    items: list[NotificacionOut]
    total: int
    no_leidas: int


class CategoriaNotificacionOut(BaseModel):
    valor: str
    etiqueta: str
