from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class PerfilOut(BaseModel):
    id: str
    nombre: str
    telefono: str | None
    email: str | None
    roles: list[str]
    fecha_registro: datetime
    # Solo relevante para `conductor` (Sección 2.2 de la spec: foto que el
    # pasajero ve al ser asignado, CU-O05 P5) -- `None` para cualquier otro rol.
    foto_url: str | None = None


# Deliberadamente sin `roles`/`forzar_cambio_password` -- nunca editables
# por autoservicio (Sección 1.3/2.2/3.1 de la spec, decisión ya confirmada:
# un usuario nunca cambia su propio rol desde esta pantalla, eso sigue
# siendo exclusivo del Módulo 1.2 de Administración).
class PerfilEditar(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=200)
    telefono: str | None = Field(default=None, min_length=7, max_length=20)
    email: EmailStr | None = None
    # Solo aplicable si el actor tiene el rol `conductor` -- `perfil/service.py`
    # lo ignora (no lo rechaza, para no acoplar el schema al rol) si no aplica.
    foto_url: str | None = Field(default=None, max_length=2000)
    # Decisión D1 del plan (PLAN_UX_COMPLEMENTARIA.md): sin OTP disponible
    # en el sistema, cambiar contacto propio exige la contraseña actual --
    # mismo nivel de exigencia que ya tiene POST /auth/cambiar-password.
    password_actual: str = Field(min_length=1, max_length=128)


class SesionOut(BaseModel):
    jti: str
    ip: str | None
    dispositivo: str | None
    ts_inicio: str | None
