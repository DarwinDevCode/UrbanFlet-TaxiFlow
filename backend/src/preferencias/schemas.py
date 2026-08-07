from typing import Literal

from pydantic import BaseModel, Field

Tema = Literal["claro", "oscuro"]
Densidad = Literal["comoda", "compacta"]


class PreferenciasOut(BaseModel):
    tema: Tema
    densidad_tablas: Densidad
    # Sección 1.4: activar/desactivar push por categoría. La taxonomía real
    # de categorías se termina de conectar en la Sección 5 del plan (Centro
    # de notificaciones) -- por ahora acepta cualquier clave string, todas
    # activas por defecto si el documento no existe.
    notificaciones_push: dict[str, bool]
    # Sección 2.3 (conductor): preferencias de turno.
    sonido_oferta: bool
    vibracion_oferta: bool
    recordatorio_turno_hora: str | None


class PreferenciasEditar(BaseModel):
    tema: Tema | None = None
    densidad_tablas: Densidad | None = None
    notificaciones_push: dict[str, bool] | None = None
    sonido_oferta: bool | None = None
    vibracion_oferta: bool | None = None
    # "HH:MM" en formato 24h, o None para desactivar el recordatorio.
    recordatorio_turno_hora: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
