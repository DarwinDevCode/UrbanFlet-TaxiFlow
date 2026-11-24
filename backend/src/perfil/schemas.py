from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class PerfilOut(BaseModel):
    id: str
    nombre: str
    telefono: str | None
    email: str | None
    roles: list[str]
    fecha_registro: datetime
    # Ronda de foto de perfil: campo general de `usuarios.foto_url`, para
    # CUALQUIER rol (antes exclusivo de `conductor`, vía `conductor.foto_url`
    # -- decisión superada, ver `perfil/service.py`). `None` cuando la cuenta
    # no tiene una foto propia; el frontend resuelve el avatar por defecto en
    # tiempo de lectura, nunca se escribe esa ruta acá.
    foto_url: str | None = None
    # Autoservicio de baja de cuenta. `None` en los 3 cuando la cuenta está
    # normal -- es la señal que usa el frontend para no pintar ningún aviso.
    baja_solicitada_en: datetime | None = None
    baja_efectiva_en: datetime | None = None
    dias_restantes_baja: int | None = None
    # Solo poblado en la respuesta de POST /perfil/baja-cuenta: placas que
    # saldrán de la flota al vencer el plazo (advertencia, no bloqueo).
    vehiculos_a_retirar: list[str] = Field(default_factory=list)


class SolicitarBajaCuentaRequest(BaseModel):
    # Motivo OPCIONAL a propósito: cerrar la propia cuenta es un derecho del
    # titular, no una acción que deba justificar (a diferencia de la baja
    # administrativa, donde el motivo sí es obligatorio porque la decide un
    # tercero sobre la cuenta de otra persona).
    motivo: str | None = None


# Deliberadamente sin `roles`/`forzar_cambio_password` -- nunca editables
# por autoservicio (Sección 1.3/2.2/3.1 de la spec, decisión ya confirmada:
# un usuario nunca cambia su propio rol desde esta pantalla, eso sigue
# siendo exclusivo del Módulo 1.2 de Administración).
class PerfilEditar(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=200)
    telefono: str | None = Field(default=None, min_length=7, max_length=20)
    email: EmailStr | None = None
    # Decisión D1 del plan (PLAN_UX_COMPLEMENTARIA.md): sin OTP disponible
    # en el sistema, cambiar contacto propio exige la contraseña actual --
    # mismo nivel de exigencia que ya tiene POST /auth/cambiar-password.
    password_actual: str = Field(min_length=1, max_length=128)


class PerfilFotoEditar(BaseModel):
    """Ronda de foto de perfil: endpoint separado de `PATCH /perfil` a
    propósito -- cambiar la foto no es una edición de contacto (D1 exige
    contraseña actual justamente porque no hay OTP para reverificar un
    teléfono/correo nuevo), es una operación de bajo riesgo y fácilmente
    reversible, así que no se le exige la misma fricción. `archivo_id=None`
    quita la foto propia (vuelve al avatar por defecto)."""

    archivo_id: str | None = Field(default=None, max_length=64)


class SesionOut(BaseModel):
    jti: str
    ip: str | None
    dispositivo: str | None
    ts_inicio: str | None
