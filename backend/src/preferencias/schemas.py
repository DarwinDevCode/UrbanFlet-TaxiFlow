from typing import Literal

from pydantic import BaseModel, Field

Tema = Literal["claro", "oscuro"]
Densidad = Literal["comoda", "compacta"]
TamanoTexto = Literal["normal", "grande", "muy_grande"]
# Segundo rediseño visual (v2): color de sidebar por cuenta, independiente
# del tema claro/oscuro -- mismo patrón que Tema/Densidad/TamanoTexto, 4
# opciones predefinidas (nunca un color libre), "claro" por defecto.
SidebarTono = Literal["claro", "ambar", "oscuro", "grafito"]

# Ronda de personalización: tope defensivo para `secciones_favoritas`. No es
# una regla de negocio (nadie marcaría 40 favoritos), es para que un cliente
# no pueda inflar el documento de preferencias sin límite.
MAX_SECCIONES_FAVORITAS = 12


class PreferenciasOut(BaseModel):
    tema: Tema
    densidad_tablas: Densidad
    tamano_texto: TamanoTexto
    sidebar_tono: SidebarTono
    secciones_favoritas: list[str]
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
    tamano_texto: TamanoTexto | None = None
    sidebar_tono: SidebarTono | None = None
    secciones_favoritas: list[str] | None = Field(default=None, max_length=MAX_SECCIONES_FAVORITAS)
    notificaciones_push: dict[str, bool] | None = None
    sonido_oferta: bool | None = None
    vibracion_oferta: bool | None = None
    # "HH:MM" en formato 24h, o None para desactivar el recordatorio.
    recordatorio_turno_hora: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
